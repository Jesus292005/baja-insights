"""How football-like the synthetic matches are, measured against approximate Premier League averages.

    python -m baja_insights realism --seeds 30

Each metric is the mean over free matches (no script), per team and match unless it says
"per match". The reference ranges are approximate public season averages, wide on purpose:
the generator should land inside them, not reproduce one season exactly.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter

from .generator import generate_match
from .roster import Roster

# metric -> (low, high, what it is)
BENCHMARKS: dict[str, tuple[float, float, str]] = {
    "goals_per_match": (2.2, 3.4, "goals per match"),
    "draw_share": (0.12, 0.35, "share of draws"),
    "passes": (350, 600, "passes"),
    "pass_accuracy": (0.75, 0.88, "share of completed passes"),
    "shots": (9, 16, "shots"),
    "shots_on_target": (3, 6, "shots on target"),
    "xg": (1.0, 1.8, "expected goals"),
    "xg_per_shot": (0.08, 0.14, "xG per shot"),
    "shots_outside_box": (0.25, 0.50, "share of shots from outside the box"),
    "fouls": (8, 14, "fouls committed"),
    "tackles": (10, 22, "tackles"),
    "recoveries": (35, 65, "ball recoveries"),
    "keeper_actions": (20, 50, "goalkeeper actions with the ball"),
    "starters": (11, 11, "players who start the match"),
}

BOX_DEPTH_M = 16.5
BOX_HALF_WIDTH_M = 20.16


def _in_box(x: float, y: float, attacks_positive: bool) -> bool:
    depth = 105 - x if attacks_positive else x
    return depth <= BOX_DEPTH_M and abs(y - 34) <= BOX_HALF_WIDTH_M


def measure(roster: Roster, seeds: range | list[int]) -> dict[str, float]:
    """Mean of every metric over free matches with the given seeds."""
    per_team: dict[str, list[float]] = {k: [] for k in BENCHMARKS if k not in ("goals_per_match", "draw_share")}
    goals, draws = [], 0
    for seed in seeds:
        events = generate_match(roster, seed=seed, script=None)
        final = events[-1]["scoreline"]
        goals.append(final["home"] + final["away"])
        draws += final["home"] == final["away"]
        starters = Counter()
        for team in (roster.home, roster.away):
            mine = [e for e in events if e["team"] == team]
            passes = [e for e in mine if e["type"] == "pass"]
            shots = [e for e in mine if e["type"] == "shot"]
            xg = sum(e["xg"] for e in shots)
            outside = sum(not _in_box(*e["start"], team == roster.home) for e in shots)
            starters[team] = sum(p.starter for p in roster.team_players(team))
            row = {
                "passes": len(passes),
                "pass_accuracy": sum(e["outcome"] == "complete" for e in passes) / max(len(passes), 1),
                "shots": len(shots),
                "shots_on_target": sum(e["outcome"] in ("goal", "saved") for e in shots),
                "xg": xg,
                "xg_per_shot": xg / len(shots) if shots else math.nan,
                "shots_outside_box": outside / len(shots) if shots else math.nan,
                "fouls": sum(e["type"] == "foul" for e in mine),
                "tackles": sum(e["type"] == "tackle" for e in mine),
                "recoveries": sum(e["type"] == "recovery" for e in mine),
                "keeper_actions": sum(e["position"] == "POR" and e["type"] in ("pass", "recovery") for e in mine),
                "starters": starters[team],
            }
            for key, value in row.items():
                if not (isinstance(value, float) and math.isnan(value)):
                    per_team[key].append(value)
    out = {key: statistics.fmean(values) for key, values in per_team.items() if values}
    out["goals_per_match"] = statistics.fmean(goals)
    out["draw_share"] = draws / len(goals)
    return out


def out_of_range(report: dict[str, float]) -> dict[str, tuple[float, float, float]]:
    """Metrics outside their reference range, as {metric: (value, low, high)}."""
    return {key: (report[key], low, high) for key, (low, high, _) in BENCHMARKS.items()
            if key in report and not low <= report[key] <= high}


def format_report(report: dict[str, float]) -> str:
    lines = [f"{'metric':22s} {'value':>8s}   reference"]
    for key, (low, high, label) in BENCHMARKS.items():
        value = report.get(key, math.nan)
        flag = "  " if low <= value <= high else "!!"
        lines.append(f"{flag}{key:20s} {value:8.2f}   {low:g}-{high:g}  {label}")
    return "\n".join(lines)
