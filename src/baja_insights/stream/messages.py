"""WebSocket messages of the stream service, as in ``contracts/stream.schema.json`` (contract v1.1).

Every message is a JSON object with ``kind``. This module is the only place that knows their shape.

    UI -> server   subscribe {match_id, from_t_s}
    server -> UI   state     {match_id, t_s, home, away, scoreline}
                   overlay   {order}
                   clock     {match_id, t_s, period, phase, speed}
                   error     {code, detail}
"""

from __future__ import annotations

import json

HALF_S = 2700
END_S = 5400

# error codes, the enum of stream.schema.json
MATCH_NOT_FOUND = "match_not_found"
STREAM_ENDED = "stream_ended"
SERVER_ERROR = "server_error"  # also for messages the server cannot read: the schema has no code for that


def phase_of(t_s: int, at_half_time: bool = False) -> str:
    """``pre`` is never sent: the clock starts with the first subscriber, already at kick-off."""
    if at_half_time or t_s == HALF_S:
        return "half_time"
    if t_s >= END_S:
        return "full_time"
    return "live"


def period_of(t_s: int, at_half_time: bool = False) -> int:
    if at_half_time or t_s == HALF_S:
        return 1  # the half_time event belongs to the first period
    return 1 if t_s < HALF_S else 2


def state(match_id: str, t_s: int, home: str, away: str, scoreline: dict) -> dict:
    return {"kind": "state", "match_id": match_id, "t_s": t_s, "home": home, "away": away,
            "scoreline": {"home": scoreline["home"], "away": scoreline["away"]}}


def overlay(order: dict) -> dict:
    return {"kind": "overlay", "order": order}


def clock(match_id: str, t_s: int, speed: float, at_half_time: bool = False) -> dict:
    return {"kind": "clock", "match_id": match_id, "t_s": t_s, "period": period_of(t_s, at_half_time),
            "phase": phase_of(t_s, at_half_time), "speed": speed}


def error(code: str, detail: str) -> dict:
    return {"kind": "error", "code": code, "detail": detail}


def encode(message: dict) -> str:
    return json.dumps(message, ensure_ascii=False, separators=(",", ":"))


def parse_subscribe(text: str) -> tuple[dict | None, dict | None]:
    """``(subscribe, None)`` or ``(None, error message)``.

    The schema requires ``from_t_s``. If a client leaves it out or sends null, it gets what is on screen now.
    """
    try:
        message = json.loads(text)
    except ValueError:
        return None, error(SERVER_ERROR, "invalid message: not JSON")
    if not isinstance(message, dict) or message.get("kind") != "subscribe":
        return None, error(SERVER_ERROR, "invalid message: the server only accepts kind 'subscribe'")
    match_id = message.get("match_id")
    if not isinstance(match_id, str) or not match_id:
        return None, error(SERVER_ERROR, "invalid message: subscribe needs match_id")
    from_t_s = message.get("from_t_s")
    if from_t_s is not None and (isinstance(from_t_s, bool) or not isinstance(from_t_s, int) or from_t_s < 0):
        return None, error(SERVER_ERROR, "invalid message: from_t_s must be a non-negative integer")
    return {"match_id": match_id, "from_t_s": from_t_s}, None
