"""Stream service: plays a match over WebSocket with its clock, scoreline and graphics orders.

    python -m baja_insights serve --data data --port 8080 --speed 1

Every viewer of a match shares one clock, which starts with the first subscriber. On ``subscribe``
the server sends ``state``, the orders the client is missing (see ``Match.orders_to_resend``) and a
``clock``; then the orders and state changes as the clock reaches them, plus a ``clock`` every real second.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from . import messages as msg
from .replay import MAX_T_S, Match, MatchClock
from .ws import ConnectionClosed, WebSocket, handshake

log = logging.getLogger(__name__)
TICK_S = 1.0  # one clock message per real second
EPSILON_S = 0.001


def load_matches(data_dir: str | Path) -> dict[str, Match]:
    """Every ``<dir>/events.jsonl`` under ``data_dir``, with ``overlays.json`` next to it when there is one."""
    matches = {}
    for events in sorted(Path(data_dir).glob("*/events.jsonl")):
        match = Match.from_files(events, events.with_name("overlays.json"))
        matches[match.match_id] = match
    return matches


class StreamServer:
    def __init__(self, matches: dict[str, Match], speed: float = 1.0, start_at: int = 0,
                 half_time_pause_s: float = 0.0, now=time.monotonic):
        self.matches = matches
        self.speed = speed
        self.start_at = start_at
        self.half_time_pause_s = half_time_pause_s
        self._now = now
        self.clocks: dict[str, MatchClock] = {}
        self.viewers = 0

    def clock_for(self, match_id: str) -> MatchClock:
        if match_id not in self.clocks:
            self.clocks[match_id] = MatchClock(self.speed, self.start_at, self.half_time_pause_s, now=self._now)
        return self.clocks[match_id]

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        ws = await handshake(reader, writer)
        if ws is None:
            return
        self.viewers += 1
        feed: asyncio.Task | None = None
        try:
            while True:
                subscribe, problem = msg.parse_subscribe(await ws.recv())
                if problem:
                    await ws.send(msg.encode(problem))
                    continue
                match = self.matches.get(subscribe["match_id"])
                if match is None:
                    await ws.send(msg.encode(msg.error(msg.MATCH_NOT_FOUND,
                                                       f"unknown match_id {subscribe['match_id']!r}")))
                    continue
                if feed:
                    feed.cancel()
                feed = asyncio.create_task(self.feed(ws, match, subscribe["from_t_s"]))
        except ConnectionClosed:
            pass
        finally:
            self.viewers -= 1
            if feed:
                feed.cancel()
            await ws.close()

    async def feed(self, ws: WebSocket, match: Match, from_t_s: int | None) -> None:
        clock = self.clock_for(match.match_id)
        clock.start()
        send = lambda m: ws.send(msg.encode(m))  # noqa: E731
        tick = lambda: msg.clock(match.match_id, clock.t_s(), clock.speed, clock.at_half_time())  # noqa: E731
        try:
            now = clock.t_s()
            await send(match.state_at(now))
            for order in match.orders_to_resend(from_t_s, now):
                await send(msg.overlay(order))
            await send(tick())
            ended = clock.finished()
            if ended:
                await send(msg.error(msg.STREAM_ENDED, "the match is over, nothing else will be sent but the clock"))
            sent_upto = now
            next_tick = self._now() + TICK_S
            while True:
                t = clock.t_s()
                if t > sent_upto:
                    for item in self._due(match, sent_upto, t):
                        await send(item)
                    sent_upto = t
                if self._now() >= next_tick - EPSILON_S:
                    await send(tick())
                    next_tick = max(next_tick + TICK_S, self._now() + EPSILON_S)
                if not ended and clock.finished():
                    ended = True
                    await send(msg.error(msg.STREAM_ENDED, "the match is over, nothing else will be sent but the clock"))
                wake = next_tick
                due = match.next_due(sent_upto)
                if due is not None and not clock.finished():
                    wake = min(wake, clock.wall_at(due) + EPSILON_S)
                if not ended:
                    wake = min(wake, clock.wall_at(MAX_T_S) + EPSILON_S)
                await asyncio.sleep(max(0.0, wake - self._now()))
        except ConnectionClosed:
            return
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - tell the UI, which keeps its last data on screen
            log.exception("stream for %s failed", match.match_id)
            try:
                await send(msg.error(msg.SERVER_ERROR, "the stream failed, subscribe again"))
            except ConnectionClosed:
                pass

    @staticmethod
    def _due(match: Match, after: int, upto: int) -> list[dict]:
        """State changes and orders in (after, upto], in time order, the state first within a second."""
        items = [(t, 0, i, match.state_at(t)) for i, t in enumerate(match.state_times(after, upto))]
        items += [(o["show_at_s"], 1, i, msg.overlay(o)) for i, o in enumerate(match.orders_between(after, upto))]
        return [m for *_, m in sorted(items, key=lambda x: x[:3])]


async def serve(data_dir: str | Path, host: str = "0.0.0.0", port: int = 8080, speed: float = 1.0,
                start_at: int = 0, half_time_pause_s: float = 0.0) -> None:
    matches = load_matches(data_dir)
    if not matches:
        raise SystemExit(f"no */events.jsonl under {data_dir}")
    server = StreamServer(matches, speed=speed, start_at=start_at, half_time_pause_s=half_time_pause_s)
    tcp = await asyncio.start_server(server.handle, host, port)
    summary = ", ".join(f"{m.match_id} ({len(m.orders)} orders)" for m in matches.values())
    log.warning("stream on ws://%s:%s, speed %sx, matches: %s", host, port, speed, summary)
    async with tcp:
        await tcp.serve_forever()
