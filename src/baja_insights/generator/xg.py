"""Small, explainable expected-goals model used by the generator.

xG = logistic(-1.2 + 1.6 * angle - 0.09 * distance - 0.4 * under_pressure - 0.3 * from_cross)

* distance: metres from the shot to the centre of the goal.
* angle: opening angle (radians) of the goal mouth seen from the shot.

Reference values: 6 m central about 0.50, penalty spot about 0.24, 25 m central about 0.05.
"""

from __future__ import annotations

import math

from ..contract import GOAL_Y, PITCH_LENGTH

GOAL_WIDTH = 7.32


def shot_geometry(progress_m: float, y: float) -> tuple[float, float]:
    dx = max(PITCH_LENGTH - progress_m, 0.5)
    dy = y - GOAL_Y
    dist = math.hypot(dx, dy)
    angle = math.atan2(GOAL_WIDTH * dx, dx * dx + dy * dy - (GOAL_WIDTH / 2) ** 2)
    if angle < 0:
        angle += math.pi
    return dist, angle


def expected_goals(progress_m: float, y: float, under_pressure: bool = False, from_cross: bool = False) -> float:
    dist, angle = shot_geometry(progress_m, y)
    z = -1.2 + 1.6 * angle - 0.09 * dist - (0.4 if under_pressure else 0.0) - (0.3 if from_cross else 0.0)
    return round(max(0.01, min(0.95, 1.0 / (1.0 + math.exp(-z)))), 2)
