"""Pure scoring functions. No state, no I/O, easy to test and to explain."""

from __future__ import annotations

import math

from ..contract import clip, distance, forward_progress
from . import params as P


def pass_difficulty(event: dict, home: str) -> float:
    """0..1 difficulty of a pass from distance, pressure, lines broken and progress."""
    if event.get("start") is None or event.get("end") is None:
        return 0.0
    w = P.PASS_DIFFICULTY_WEIGHTS
    dist = distance(event["start"], event["end"])
    prog = forward_progress(event["start"], event["end"], event["team"], home)
    value = (
        w["distance"] * min(dist / P.PASS_DISTANCE_REF_M, 1.0)
        + w["pressure"] * (1.0 if event.get("under_pressure") else 0.0)
        + w["lines"] * min((event.get("lines_broken") or 0) / 2.0, 1.0)
        + w["progress"] * clip(prog / P.PASS_PROGRESS_REF_M, 0.0, 1.0)
    )
    return round(value, 2)


def is_progressive(event: dict, home: str) -> bool:
    if event.get("type") != "pass" or event.get("outcome") != "complete" or event.get("end") is None:
        return False
    return forward_progress(event["start"], event["end"], event["team"], home) >= P.PROGRESSIVE_PASS_MIN_M


def expected_for_role(baseline: dict[str, float], minutes: float) -> dict[str, float]:
    return {k: baseline.get(k, 0.0) * minutes / 90.0 for k in P.ROLE_STATS}


def vs_role(actual: dict[str, float], baseline: dict[str, float], minutes: float) -> float:
    """Mean relative difference against the role baseline, clipped to [-1, 1].

    Each stat contributes (actual - expected) / max(expected, 1), clipped to
    [-1, 2] so a single stat cannot dominate. 0 means "exactly what a player in
    this role usually does in this many minutes".
    """
    if minutes <= 0:
        return 0.0
    expected = expected_for_role(baseline, minutes)
    terms = []
    for key in P.ROLE_STATS:
        exp = expected[key]
        term = (actual.get(key, 0.0) - exp) / max(exp, P.ROLE_EXPECTED_FLOOR)
        terms.append(clip(term, *P.ROLE_TERM_CLIP))
    return round(clip(sum(terms) / len(terms), -1.0, 1.0), 2)


def mvp_score(raw_points: float, role_delta: float, minutes: float) -> float:
    """0..10 saturating score from raw points plus the role adjustment."""
    adjusted = raw_points + P.MVP_ROLE_WEIGHT * role_delta * min(minutes, 90.0) / 90.0
    return round(10.0 * (1.0 - math.exp(-max(adjusted, 0.0) / P.MVP_SCALE)), 1)


def duel_bar(a_vs_role: float, b_vs_role: float) -> float:
    """-1 (player B clearly ahead) .. +1 (player A clearly ahead)."""
    return round(clip((a_vs_role - b_vs_role) / 2.0, -1.0, 1.0), 2)


# --- Priorities --------------------------------------------------------------

def priority_mvp(from_rank: int, to_rank: int) -> float:
    value = 0.45 + 0.04 * max(from_rank - to_rank, 0) + (0.30 if to_rank == 1 else 0.0)
    return round(min(value, 0.95), 2)


def priority_duel(bar: float, flipped: bool) -> float:
    return round(0.35 + 0.20 * abs(bar) + (0.15 if flipped else 0.0), 2)


def priority_card(delta: int) -> float:
    return round(min(0.5 + 0.1 * delta, 0.9), 2)


def priority_milestone(role_delta: float) -> float:
    return round(0.5 + 0.45 * clip(role_delta, 0.0, 1.0), 2)


def priority_phase(label: str) -> float:
    return round(0.5 + (0.1 if label == "pressure_shift" else 0.0), 2)


# --- Goal chain ----------------------------------------------------------------

def chain_weight(event: dict, is_assist: bool) -> float:
    w = P.CHAIN_WEIGHTS
    kind = event["type"]
    if kind == "recovery":
        return w["recovery"]
    if kind == "tackle" and event.get("outcome") == "won":
        return w["tackle"]
    if kind == "pass" and event.get("outcome") == "complete":
        return (w["pass_base"] + w["pass_per_line"] * (event.get("lines_broken") or 0)
                + (w["pass_pressure"] if event.get("under_pressure") else 0.0)
                + (w["assist"] if is_assist else 0.0))
    if kind == "off_ball_run" and event.get("dragged_defender"):
        return min(w["off_ball_run_per_m"] * (event.get("space_opened_m") or 0.0), w["off_ball_run_cap"])
    if kind == "shot":
        return w["shot"]
    return 0.0


def split_credit(weights: list[float]) -> list[float]:
    """Normalise to 1.00 with two decimals (largest remainder), so it always sums to 1."""
    total = sum(weights)
    if total <= 0:
        return [0.0 for _ in weights]
    raw = [w / total * 100 for w in weights]
    floors = [math.floor(r) for r in raw]
    missing = 100 - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in order[:missing]:
        floors[i] += 1
    return [f / 100 for f in floors]


def chain_action_label(event: dict) -> str:
    kind = event["type"]
    if kind == "recovery":
        return "recuperación"
    if kind == "tackle":
        return "entrada ganada"
    if kind == "shot":
        return "remate"
    if kind == "off_ball_run":
        return "desmarque y arrastre de marca"
    if kind == "pass":
        if event.get("cross"):
            return "centro"
        lines = event.get("lines_broken") or 0
        if lines >= 2:
            return f"pase que rompió {lines} líneas"
        if lines == 1:
            return "pase que rompió 1 línea"
        return "pase"
    return kind
