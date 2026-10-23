"""Shared conventions of contract v1: pitch, clock, enums and small helpers.

Everything here mirrors ``contracts/README.md``. If you change a value here,
change the document and the JSON Schemas in ``contracts/`` in the same commit.
"""

from __future__ import annotations

import math
from typing import Iterable

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
HALF_LENGTH = PITCH_LENGTH / 2
GOAL_Y = PITCH_WIDTH / 2
GOAL_HALF_WIDTH = 3.66

MATCH_LENGTH_S = 90 * 60
HALF_LENGTH_S = 45 * 60

EVENT_TYPES = (
    "match_start", "pass", "shot", "tackle", "recovery", "duel", "pressure",
    "foul", "goal", "substitution", "off_ball_run", "half_time",
    "second_half_start", "match_end",
)
STRUCTURAL_EVENTS = ("match_start", "half_time", "second_half_start", "match_end", "substitution")
DEFENSIVE_EVENTS = ("pressure", "tackle", "foul")
DEF_ACTION_EVENTS = ("recovery", "tackle", "pressure", "duel")

INSIGHT_TYPES = (
    "mvp_rank_change", "duel_state", "standout_milestone", "card_upgrade",
    "goal_chain", "team_phase", "match_keys", "top3", "match_summary",
)
OVERLAY_TYPES = (
    "mvp_update", "duel_bar", "standout_milestone", "card_upgrade",
    "goal_analysis", "team_phase", "match_keys", "top3", "chat_answer",
)
SLOTS = ("top_right", "lower_third", "side_panel", "bottom_bar", "center", "full_screen")
POSITIONS = ("POR", "LD", "LI", "DFC", "MCD", "MC", "ED", "EI", "DC")
CARD_ATTRIBUTES = ("ritmo", "disparo", "vision", "regate", "defensa", "fisico", "sin_balon")

# Bahía FC (home) always attacks towards x = 105, Real Cardón (away) towards x = 0.
# The generator keeps that convention for any match: home attacks to +x.


def t_s(minute: int, second: int) -> int:
    """Continuous match second. The second half starts at 45:00 (2700 s)."""
    return int(minute) * 60 + int(second)


def event_t_s(event: dict) -> int:
    return event["t_s"] if event.get("t_s") is not None else t_s(event["minute"], event["second"])


def fmt_clock(seconds: int) -> str:
    """2022 -> '33:42'. Minutes are not wrapped, so 3791 -> '63:11'."""
    seconds = int(seconds)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def parse_clock(value: str | int | float) -> int:
    """Accept '63:09', '63', 3789 or '3789s' and return match seconds."""
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().lower().rstrip("s")
    if ":" in text:
        minute, second = text.split(":", 1)
        return int(minute) * 60 + int(second)
    number = int(text)
    # A bare number up to 90 is read as a minute, anything larger as seconds.
    return number * 60 if number <= 90 else number


def period_of(seconds: int) -> int:
    return 1 if seconds < HALF_LENGTH_S else 2


def attacks_positive(team: str, home: str) -> bool:
    return team == home


def progress_from_own_goal(x: float, team: str, home: str) -> float:
    """Distance (m) from the team's own goal line along the attacking axis."""
    return x if attacks_positive(team, home) else PITCH_LENGTH - x


def forward_progress(start: Iterable[float], end: Iterable[float], team: str, home: str) -> float:
    sx = list(start)[0]
    ex = list(end)[0]
    return ex - sx if attacks_positive(team, home) else sx - ex


def in_opponent_half(x: float, team: str, home: str) -> bool:
    return progress_from_own_goal(x, team, home) > HALF_LENGTH


def distance(a: Iterable[float], b: Iterable[float]) -> float:
    ax, ay = list(a)
    bx, by = list(b)
    return math.hypot(bx - ax, by - ay)


def clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
