"""python -m baja_agents run | audit | serve | ask"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from baja_insights.cli import read_events
from baja_insights.engine.tools import MatchQuery
from baja_insights.roster import Roster

from . import config
from .config import CONTRACTS, REPO_ROOT, Settings
from .pipeline import Crew


def validate(overlays: list[dict]) -> list[str]:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return []
    schema = json.loads((CONTRACTS / "overlay.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return [f"{o['overlay_id']}: {e.message}" for o in overlays for e in validator.iter_errors(o)]


def cmd_run(args) -> int:
    insights_path = Path(args.insights)
    insights = json.loads(insights_path.read_text(encoding="utf-8"))
    out = Path(args.out) if args.out else insights_path.with_name("overlays.json")
    report_path = Path(args.report) if args.report else insights_path.with_name("agents_report.json")

    settings = Settings(max_calls=args.max_calls)
    if args.no_cache:
        settings.cache_dir = None
    roster = Roster.load(args.teams)
    events = Path(args.events) if args.events else insights_path.with_name("events.jsonl")
    query = MatchQuery(read_events(events), roster) if events.exists() else None
    crew = Crew(roster, insights[0]["match_id"], settings, offline=args.offline, query=query)
    overlays, report = asyncio.run(crew.run_match(insights))

    errors = validate(overlays)
    out.write_text(json.dumps(overlays, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    calls = report["model_calls"]
    print(f"{len(overlays)} overlays from {report['graphics']} graphics and {report['duel_frames']} duel bar frames -> {out}")
    print(f"versions written by agents: {report['versions_by_agent']}, by templates: {report['versions_by_template']}")
    print(f"model calls: {calls['calls']} (cache hits {calls['cache_hits']}, failures {calls['failures']}, "
          f"skipped {calls['skipped']}) -> {report_path}")
    for error in errors[:20]:
        print("schema:", error)
    return 1 if errors else 0


def cmd_audit(args) -> int:
    insights = json.loads(Path(args.insights).read_text(encoding="utf-8"))
    overlays_path = Path(args.overlays) if args.overlays else Path(args.insights).with_name("overlays.json")
    overlays = json.loads(overlays_path.read_text(encoding="utf-8"))
    crew = Crew(Roster.load(args.teams), insights[0]["match_id"], Settings())
    findings = asyncio.run(crew.audit(overlays, insights))
    for finding in sorted(findings, key=lambda f: f["clock"]):
        for key, problems in finding["problems"].items():
            print(f"{finding['clock']} {finding['insight_id']} {key}: {finding['texts'][key]['text']}")
            for problem in problems:
                print(f"    - {problem}")
    graphics = len({o["source_insight"] for o in overlays if o["source_insight"]})
    print(f"\n{len(findings)} of {graphics} graphics with problems, {crew.runner.stats.calls} model calls")
    return 1 if findings else 0


def make_chat(args):
    """Ask the match with its own call budget and cache. Settings come from flags or environment variables."""
    from .ask import AskTheMatch, load_matches
    from .llm import LLMRunner

    cache = Path(args.cache_dir or os.environ.get("CHAT_CACHE_DIR") or config.DEFAULT_CACHE_DIR)
    runner = LLMRunner(max_calls=int(os.environ.get("CHAT_MAX_CALLS", 3000)), timeout_s=40, concurrency=4,
                       cache_dir=None, model=config.model_name(), reasoning_effort=config.reasoning_effort())
    return AskTheMatch(load_matches(Path(args.data), args.teams), runner, client=config.make_client(),
                       cache_dir=cache, per_minute=int(os.environ.get("CHAT_PER_MINUTE", 20)))


def cmd_serve(args) -> int:
    from .server import serve

    serve(make_chat(args), args.host, args.port)
    return 0


def cmd_ask(args) -> int:
    chat = make_chat(args)
    request = {"match_id": args.match, "question": args.question, "at": args.at, "mode": args.mode,
               "language": args.language}
    print(json.dumps(asyncio.run(chat.ask(request)), ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(prog="baja_agents")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="turn a match's insights into graphics orders")
    run.add_argument("--insights", default=str(REPO_ROOT / "data" / "m001" / "insights.json"))
    run.add_argument("--out", help="default: overlays.json next to the insights")
    run.add_argument("--report", help="default: agents_report.json next to the insights")
    run.add_argument("--teams", help="teams.json, default: mocks/teams.json")
    run.add_argument("--events", help="events.jsonl for the duel bar frames, default: next to the insights")
    run.add_argument("--offline", action="store_true", help="no model calls, templates and cache only")
    run.add_argument("--max-calls", type=int, default=Settings.max_calls)
    run.add_argument("--no-cache", action="store_true")
    audit = sub.add_parser("audit", help="fact-check graphics already generated with the verifier agent")
    audit.add_argument("--insights", default=str(REPO_ROOT / "data" / "m001" / "insights.json"))
    audit.add_argument("--overlays", help="default: overlays.json next to the insights")
    audit.add_argument("--teams", help="teams.json, default: mocks/teams.json")
    for name, help_text in (("serve", "HTTP service for POST /api/ask"), ("ask", "ask the match one question")):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("--data", default=os.environ.get("CHAT_DATA_DIR", str(REPO_ROOT / "data")),
                         help="folder with one <match>/events.jsonl per match")
        cmd.add_argument("--teams", default=os.environ.get("CHAT_TEAMS"), help="teams.json, default: mocks/teams.json")
        cmd.add_argument("--cache-dir", help="default: CHAT_CACHE_DIR or agents/.cache")
        if name == "serve":
            cmd.add_argument("--host", default="0.0.0.0")
            cmd.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)))
        else:
            cmd.add_argument("question")
            cmd.add_argument("--match", default="m001")
            cmd.add_argument("--at", default="45:00")
            cmd.add_argument("--mode", choices=["fan", "analyst"], default="fan")
            cmd.add_argument("--language", choices=["es", "en"], default="es")
    args = parser.parse_args(argv)
    commands = {"run": cmd_run, "audit": cmd_audit, "serve": cmd_serve, "ask": cmd_ask}
    return commands[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
