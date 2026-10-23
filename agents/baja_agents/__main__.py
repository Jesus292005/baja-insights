"""python -m baja_agents run [--insights ...] [--out ...] [--offline]"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from baja_insights.cli import read_events
from baja_insights.engine.tools import MatchQuery
from baja_insights.roster import Roster

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
    args = parser.parse_args(argv)
    return cmd_run(args) if args.command == "run" else cmd_audit(args)


if __name__ == "__main__":
    raise SystemExit(main())
