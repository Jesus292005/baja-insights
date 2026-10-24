"""WebSocket messages of the stream service (contract v1.1, ``contracts/stream.schema.json``).

Every message is a JSON object with ``type``. This module is the only place that
knows their shape, so adjusting to the final schema means changing it here.

    UI -> server   subscribe {match_id, from_t_s}
    server -> UI   state     {t_s, home, away, scoreline}
                   overlay   {order}
                   clock     {t_s, period, phase, speed}
                   error     {code, detail}
"""

from __future__ import annotations

import json

HALF_S = 2700
END_S = 5400

# error codes
INVALID_MESSAGE = "invalid_message"
MATCH_NOT_FOUND = "match_not_found"


def period_of(t_s: int) -> int:
    return 1 if t_s < HALF_S else 2


def phase_of(t_s: int) -> str:
    if t_s < HALF_S:
        return "first_half"
    if t_s < END_S:
        return "second_half"
    return "full_time"


def state(t_s: int, home: str, away: str, scoreline: dict) -> dict:
    return {"type": "state", "t_s": t_s, "home": home, "away": away,
            "scoreline": {"home": scoreline["home"], "away": scoreline["away"]}}


def overlay(order: dict) -> dict:
    return {"type": "overlay", "order": order}


def clock(t_s: int, speed: float) -> dict:
    return {"type": "clock", "t_s": t_s, "period": period_of(t_s), "phase": phase_of(t_s), "speed": speed}


def error(code: str, detail: str) -> dict:
    return {"type": "error", "code": code, "detail": detail}


def encode(message: dict) -> str:
    return json.dumps(message, ensure_ascii=False, separators=(",", ":"))


def parse_subscribe(text: str) -> tuple[dict | None, dict | None]:
    """``(subscribe, None)`` or ``(None, error message)``. ``from_t_s`` may be missing or null."""
    try:
        message = json.loads(text)
    except ValueError:
        return None, error(INVALID_MESSAGE, "not JSON")
    if not isinstance(message, dict) or message.get("type") != "subscribe":
        return None, error(INVALID_MESSAGE, "the only message the server accepts is subscribe")
    match_id = message.get("match_id")
    if not isinstance(match_id, str) or not match_id:
        return None, error(INVALID_MESSAGE, "subscribe needs match_id")
    from_t_s = message.get("from_t_s")
    if from_t_s is not None and (isinstance(from_t_s, bool) or not isinstance(from_t_s, int) or from_t_s < 0):
        return None, error(INVALID_MESSAGE, "from_t_s must be a non-negative integer or null")
    return {"match_id": match_id, "from_t_s": from_t_s}, None
