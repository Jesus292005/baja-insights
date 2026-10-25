"""What the stream sends and when, without any network: one match, its events and its orders.

The scoreline comes from the ``goal``, ``half_time`` and ``match_end`` events, never from the orders.
"""

from __future__ import annotations

import bisect
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..cli import read_events
from . import messages as msg

MAX_T_S = 5520  # last second an order can be shown (overlay.schema.json, show_at_s)
STATE_EVENTS = ("goal", "half_time", "match_end")


@dataclass
class Match:
    match_id: str
    home: str
    away: str
    score_changes: list[tuple[int, dict]]  # (t_s, scoreline), in time order, starting at 0-0
    orders: list[dict]                       # sorted by show_at_s
    _order_times: list[int] = field(init=False, repr=False)

    def __post_init__(self):
        self.orders = sorted(self.orders, key=lambda o: (o["show_at_s"], o["overlay_id"]))
        self._order_times = [o["show_at_s"] for o in self.orders]

    @classmethod
    def from_files(cls, events_path: str | Path, overlays_path: str | Path | None = None) -> "Match":
        import json

        events = read_events(events_path)
        start = next(e for e in events if e["type"] == "match_start")
        changes = [(0, {"home": 0, "away": 0})]
        for e in events:
            if e["type"] in STATE_EVENTS and e.get("scoreline"):
                changes.append((e["t_s"], dict(e["scoreline"])))
        orders = []
        if overlays_path and Path(overlays_path).exists():
            orders = json.loads(Path(overlays_path).read_text(encoding="utf-8"))
        return cls(start["match_id"], start["home"], start["away"], changes, orders)

    def scoreline_at(self, t_s: int) -> dict:
        current = self.score_changes[0][1]
        for when, scoreline in self.score_changes:
            if when > t_s:
                break
            current = scoreline
        return current

    def state_at(self, t_s: int) -> dict:
        return msg.state(self.match_id, t_s, self.home, self.away, self.scoreline_at(t_s))

    def state_times(self, after: int, upto: int) -> list[int]:
        """Seconds in (after, upto] with a state-changing event (goal, half time, end)."""
        return sorted({t for t, _ in self.score_changes[1:] if after < t <= upto})

    def orders_between(self, after: int, upto: int) -> list[dict]:
        """Orders with show_at_s in (after, upto]."""
        lo = bisect.bisect_right(self._order_times, after)
        hi = bisect.bisect_right(self._order_times, upto)
        return self.orders[lo:hi]

    def orders_to_resend(self, from_t_s: int | None, now: int) -> list[dict]:
        """Orders already due at ``now`` that the client has not finished seeing.

        An order counts while it is on screen, ``show_at_s + duration_s > from_t_s``, so a graphic that
        was showing when the connection dropped comes back. Without ``from_t_s`` (a first subscribe),
        only what is on screen right now.
        """
        since = now if from_t_s is None else min(from_t_s, now)
        return [o for o in self.orders_between(-1, now) if o["show_at_s"] + o["duration_s"] > since]

    def next_due(self, after: int) -> int | None:
        """First second after ``after`` with an order or a state change."""
        candidates = []
        i = bisect.bisect_right(self._order_times, after)
        if i < len(self._order_times):
            candidates.append(self._order_times[i])
        candidates += [t for t, _ in self.score_changes[1:] if t > after][:1]
        return min(candidates) if candidates else None


class MatchClock:
    """Shared match clock: every viewer of a match sees the same minute, like a live broadcast.

    It starts when ``start()`` is first called (the first subscriber) at ``start_at`` match seconds and
    runs at ``speed`` match seconds per real second, up to ``MAX_T_S`` so the full-time graphics play.
    With ``half_time_pause_s`` it stops at 45:00 for that many real seconds, in phase ``half_time``.
    """

    def __init__(self, speed: float = 1.0, start_at: int = 0, half_time_pause_s: float = 0.0, now=time.monotonic):
        if speed <= 0:
            raise ValueError("speed must be > 0")
        if half_time_pause_s < 0:
            raise ValueError("half_time_pause_s must be >= 0")
        self.speed = speed
        self.start_at = start_at
        self._now = now
        self._wall0: float | None = None
        # real seconds from the start until the clock reaches 45:00, if it has a pause to make there
        has_pause = half_time_pause_s > 0 and start_at < msg.HALF_S
        self._pause = half_time_pause_s if has_pause else 0.0
        self._to_half = (msg.HALF_S - start_at) / speed if has_pause else 0.0

    @property
    def started(self) -> bool:
        return self._wall0 is not None

    def start(self) -> None:
        if self._wall0 is None:
            self._wall0 = self._now()

    def _elapsed(self) -> float:
        return 0.0 if self._wall0 is None else self._now() - self._wall0

    def at_half_time(self) -> bool:
        return self._pause > 0 and self.started and self._to_half <= self._elapsed() < self._to_half + self._pause

    def t(self) -> float:
        """Match seconds, as a float."""
        e = self._elapsed()
        if self._pause and e >= self._to_half:
            e = max(self._to_half, e - self._pause)
        return min(float(MAX_T_S), self.start_at + e * self.speed)

    def t_s(self) -> int:
        return int(self.t())

    def wall_at(self, t_s: float) -> float:
        """Real (monotonic) time at which the clock reaches ``t_s``."""
        assert self._wall0 is not None
        wall = self._wall0 + (t_s - self.start_at) / self.speed
        return wall + self._pause if self._pause and t_s > msg.HALF_S else wall

    def finished(self) -> bool:
        return self.t() >= MAX_T_S
