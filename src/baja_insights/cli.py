"""Command line entry point.

    python -m baja_insights generate --seed 23 --script m001 --out data/m001/events.jsonl
    python -m baja_insights analyze  --events data/m001/events.jsonl --out data/m001/insights.json
    python -m baja_insights stream   --events data/m001/events.jsonl --speed 60
    python -m baja_insights ask      --events data/m001/events.jsonl get_mvp_ranking '{"at": "35:00", "top": 3}'
    python -m baja_insights validate data/m001/events.jsonl data/m001/insights.json
    python -m baja_insights serve    --data data --port 8080 --speed 1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from .contract import event_t_s
from .engine import InsightEngine
from .engine.tools import MatchQuery
from .generator import generate_match
from .roster import Roster

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


def read_events(path: str | Path) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8")
    if text.lstrip().startswith("["):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def write_json(path: str | Path, data, jsonl: bool = False) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if jsonl:
        path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in data), encoding="utf-8")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_generate(args) -> int:
    roster = Roster.load(args.teams)
    script = None if args.script in (None, "none", "free") else args.script
    events = generate_match(roster, seed=args.seed, script=script, match_id=args.match_id)
    write_json(args.out, events, jsonl=str(args.out).endswith(".jsonl"))
    goals = [e for e in events if e["type"] == "goal"]
    print(f"{len(events)} events, final {events[-1]['scoreline']}, goals at "
          f"{[e['minute'] for e in goals]} -> {args.out}", file=sys.stderr)
    return 0


def cmd_analyze(args) -> int:
    roster = Roster.load(args.teams)
    insights = InsightEngine(roster).run(read_events(args.events))
    write_json(args.out, insights, jsonl=str(args.out).endswith(".jsonl"))
    print(f"{len(insights)} insights -> {args.out}", file=sys.stderr)
    return 0


def cmd_stream(args) -> int:
    """Replay events in (accelerated) real time and print each insight as JSONL as it appears."""
    roster = Roster.load(args.teams)
    engine = InsightEngine(roster)
    events = read_events(args.events)
    start_wall = time.monotonic()
    for event in events:
        if args.speed > 0:
            due = event_t_s(event) / args.speed
            delay = due - (time.monotonic() - start_wall)
            if delay > 0:
                time.sleep(delay)
        try:
            for insight in engine.process(event):
                sys.stdout.write(json.dumps(insight, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except BrokenPipeError:  # e.g. piped into `head`
            return 0
    return 0


def cmd_ask(args) -> int:
    query = MatchQuery(read_events(args.events), Roster.load(args.teams))
    arguments = json.loads(args.arguments) if args.arguments else {}
    print(json.dumps(query.dispatch(args.tool, arguments), ensure_ascii=False, indent=2))
    return 0


def cmd_validate(args) -> int:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:  # pragma: no cover
        print("pip install jsonschema", file=sys.stderr)
        return 2
    schemas = {name: Draft202012Validator(json.loads((CONTRACTS / f"{name}.schema.json").read_text(encoding="utf-8")))
               for name in ("event", "insight", "overlay")}
    failed = 0
    for path in args.files:
        items = read_events(path)
        first = items[0] if items else {}
        kind = "insight" if "insight_id" in first else "overlay" if "overlay_id" in first else "event"
        errors = [(i, e.message) for i, item in enumerate(items) for e in schemas[kind].iter_errors(item)]
        failed += bool(errors)
        status = "OK" if not errors else f"{len(errors)} errors"
        print(f"{path}: {len(items)} {kind}s, {status}")
        for i, message in errors[:10]:
            print(f"  item {i}: {message}")
    return 1 if failed else 0


def cmd_serve(args) -> int:
    import asyncio
    import logging

    from .stream import serve

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(serve(args.data, args.host, args.port, args.speed, args.start_at))
    except KeyboardInterrupt:
        pass
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="baja_insights", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--teams", default=None, help="teams.json (default: mocks/teams.json)")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="generate a synthetic match")
    g.add_argument("--seed", type=int, default=23)
    g.add_argument("--script", default="m001", help="script name or path, or 'free' for an unscripted match")
    g.add_argument("--match-id", default=None)
    g.add_argument("--out", required=True)
    g.set_defaults(func=cmd_generate)

    a = sub.add_parser("analyze", help="run the insight engine over a match")
    a.add_argument("--events", required=True)
    a.add_argument("--out", required=True)
    a.set_defaults(func=cmd_analyze)

    s = sub.add_parser("stream", help="replay a match and print insights live")
    s.add_argument("--events", required=True)
    s.add_argument("--speed", type=float, default=60.0, help="match seconds per real second, 0 = no waiting")
    s.set_defaults(func=cmd_stream)

    q = sub.add_parser("ask", help="call one of the chat query functions")
    q.add_argument("--events", required=True)
    q.add_argument("tool")
    q.add_argument("arguments", nargs="?", default="{}")
    q.set_defaults(func=cmd_ask)

    v = sub.add_parser("validate", help="validate JSON/JSONL files against the contracts")
    v.add_argument("files", nargs="+")
    v.set_defaults(func=cmd_validate)

    w = sub.add_parser("serve", help="WebSocket stream for the UI: clock, scoreline and graphics orders")
    w.add_argument("--data", default=str(Path(__file__).resolve().parents[2] / "data"),
                   help="folder with one <match>/events.jsonl (+ overlays.json) per match")
    w.add_argument("--host", default="0.0.0.0")
    w.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    w.add_argument("--speed", type=float, default=float(os.environ.get("STREAM_SPEED", "1")),
                   help="match seconds per real second")
    w.add_argument("--start-at", type=int, default=0, help="match second where the clock starts")
    w.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
