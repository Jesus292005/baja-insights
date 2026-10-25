"""From insight to graphics order: type, slot, timing, card and data. All deterministic.

The agents only write ``title`` and ``text``. Everything else in an overlay is
copied from the insight here, so the numbers on screen are the engine's.
"""

from __future__ import annotations

import hashlib

from baja_insights.contract import fmt_clock
from baja_insights.roster import Roster

from .models import VARIANT_KEYS

# insight type -> (overlay type, slot, seconds on screen)
LAYOUT = {
    "mvp_rank_change": ("mvp_update", "top_right", 7),
    "duel_state": ("duel_bar", "bottom_bar", 8),
    "standout_milestone": ("standout_milestone", "side_panel", 9),
    "card_upgrade": ("card_upgrade", "lower_third", 6),
    "goal_chain": ("goal_analysis", "center", 10),
    "team_phase": ("team_phase", "side_panel", 8),
    "match_keys": ("match_keys", "side_panel", 15),
    "top3": ("top3", "full_screen", 20),
}
LATENCY_S = 2        # time from the play to the graphic
MAX_DELAY_S = 20     # an optional graphic that would wait longer for its slot is dropped
MAX_SHOW_AT_S = 5520
BLOCKING_SLOTS = ("center", "full_screen")  # while they are on, nothing else is


def card_for(insight: dict, roster: Roster) -> dict | None:
    facts = insight["facts"]
    if insight["type"] == "card_upgrade":
        change, name = facts, facts["player"]
    elif insight["type"] in ("mvp_rank_change", "standout_milestone") and facts.get("card_change"):
        change, name = facts["card_change"], facts["player"]
    else:
        return None
    player = roster.find(name)
    if player is None:
        return None
    return {"player": player.name, "team": player.team, "position": facts.get("position", player.position),
            "attribute": change["attribute"], "from": change["from"], "to": change["to"], "delta": change["delta"],
            "overall_from": change["overall_from"], "overall_to": change["overall_to"], "reason": change["reason"],
            # v1.1, only when the engine sends them: a null reason_code would break the schema's enum
            **{k: change[k] for k in ("reason_code", "reason_params") if k in change}}


def data_for(insight: dict) -> dict | None:
    facts, kind = insight["facts"], insight["type"]
    if kind == "mvp_rank_change":
        data = {"rank": facts["to_rank"], "previous_rank": facts["from_rank"], "mvp_score": facts["mvp_score"]}
        if facts.get("ranking"):  # v1.1, once the engine emits it
            data["ranking"] = [dict(item) for item in facts["ranking"]]
        return data
    if kind == "duel_state":
        return {"player_a": facts["player_a"], "player_b": facts["player_b"], "bar": facts["bar"]}
    if kind == "standout_milestone":
        return {**facts["stats"], "vs_role": facts["vs_role"], "mvp_rank": facts["mvp_rank"]}
    if kind == "goal_chain":
        data = {"chain": [link["player"] for link in facts["chain"]],
                "credit": [link["credit"] for link in facts["chain"]],
                "chain_detail": [dict(link) for link in facts["chain"]],
                "scoreline": facts["scoreline"], "xg": facts["xg"]}
        if facts.get("invisible_assist"):
            data["invisible_assist"] = facts["invisible_assist"]
        return data
    if kind == "team_phase":
        return {k: v for k, v in facts.items() if k != "window"}
    if kind == "match_keys":
        return {"scoreline": facts["scoreline"], "xg": facts["xg"], "possession_pct": facts["possession_pct"]}
    if kind == "top3":
        return {"cards": [{"rank": c["rank"], "player": c["player"], "team": c["team"],
                           "position": c["position"], "mvp_score": c["mvp_score"]} for c in facts["top3"]],
                "final_scoreline": facts["final_scoreline"]}
    return None


def duration_for(insight: dict) -> int:
    _, _, seconds = LAYOUT[insight["type"]]
    if insight["type"] == "goal_chain" and insight["facts"].get("invisible_assist"):
        seconds += 2  # one more beat to show the run without the ball
    return seconds


class Scheduler:
    """Keeps graphics in the same slot from overlapping. Center and full screen block every slot."""

    def __init__(self):
        self.busy_until: dict[str, int] = {}

    def place(self, insight: dict, must_show: bool) -> int | None:
        _, slot, _ = LAYOUT[insight["type"]]
        start = insight["t_s"] + LATENCY_S
        blockers = [self.busy_until.get(s, 0) for s in BLOCKING_SLOTS]
        start = max(start, self.busy_until.get(slot, 0), *blockers)
        if not must_show and start - insight["t_s"] > MAX_DELAY_S:
            return None
        start = min(start, MAX_SHOW_AT_S)
        end = start + duration_for(insight)
        self.busy_until[slot] = max(self.busy_until.get(slot, 0), end)
        if slot in BLOCKING_SLOTS:
            for other in {s for _, s, _ in LAYOUT.values()}:
                self.busy_until[other] = max(self.busy_until.get(other, 0), end)
        return start


def build(insight: dict, texts: dict[str, dict], show_at_s: int, roster: Roster) -> list[dict]:
    """Four overlays (fan/analyst x es/en) for one insight. ``texts`` maps 'fan_es' -> {title, text}."""
    overlay_type, slot, _ = LAYOUT[insight["type"]]
    card, data = card_for(insight, roster), data_for(insight)
    out = []
    for key in VARIANT_KEYS:
        mode, language = key.split("_")
        overlay = {
            "overlay_id": "",
            "match_id": insight["match_id"],
            "source_insight": insight["insight_id"],
            "period": insight["period"],
            "show_at": fmt_clock(show_at_s),
            "show_at_s": show_at_s,
            "duration_s": duration_for(insight),
            "slot": slot,
            "mode": mode,
            "language": language,
            "type": overlay_type,
            "title": texts[key]["title"],
            "text": texts[key]["text"],
            "evidence": list(insight["evidence"]),
        }
        if card:
            overlay["card"] = card
        if data is not None:
            overlay["data"] = data
        out.append(overlay)
    return out


FRAME_EVERY_S = 300
FRAME_DURATION_S = 4
FRAME_MIN_CHANGE = 0.05  # smaller moves of the bar are noise on screen


def _busy(overlays: list[dict]) -> list[tuple[str, int, int]]:
    seen, out = set(), []
    for o in overlays:
        key = (o["source_insight"], o["show_at_s"], o["slot"])
        if key not in seen:
            seen.add(key)
            out.append((o["slot"], o["show_at_s"], o["show_at_s"] + o["duration_s"]))
    return out


def duel_frames(overlays: list[dict], get_duel, match_id: str, every_s: int = FRAME_EVERY_S,
                end_s: int = 5400) -> list[dict]:
    """Duel bar frames between notices, for every viewer (mode and language 'all').

    Every ``every_s`` seconds the bar of the last duel shown on screen is refreshed with the
    engine's value at that moment (``get_duel(player_a, player_b, t_s)`` returns ``duel_state`` facts).
    A frame is skipped before the first duel notice, when the bar barely moved, or when its slot is busy.
    """
    notices = sorted((o for o in overlays if o["type"] == "duel_bar" and o["source_insight"]),
                     key=lambda o: o["show_at_s"])
    busy = _busy(overlays)
    last_frame: dict[tuple[str, str], tuple[int, float]] = {}
    frames = []
    for t in range(every_s, end_s, every_s):
        shown = [o for o in notices if o["show_at_s"] < t]
        if not shown:
            continue
        latest = shown[-1]
        pair = (latest["data"]["player_a"], latest["data"]["player_b"])
        on_screen = latest["data"]["bar"]
        if pair in last_frame and last_frame[pair][0] > latest["show_at_s"]:
            on_screen = last_frame[pair][1]
        if any(slot in ("bottom_bar", *BLOCKING_SLOTS) and start < t + FRAME_DURATION_S and t < end
               for slot, start, end in busy):
            continue
        facts = get_duel(pair[0], pair[1], t)
        if "error" in facts or abs(facts["bar"] - on_screen) < FRAME_MIN_CHANGE:
            continue
        last_frame[pair] = (t, facts["bar"])
        frames.append({
            "overlay_id": "", "match_id": match_id, "source_insight": None,
            "period": 1 if t < 2700 else 2, "show_at": fmt_clock(t), "show_at_s": t,
            "duration_s": FRAME_DURATION_S, "slot": "bottom_bar", "mode": "all", "language": "all",
            "type": "duel_bar", "title": None, "text": None,
            "data": {"player_a": pair[0], "player_b": pair[1], "bar": facts["bar"]},
        })
    return frames


CHAT_SLOT = "side_panel"
CHAT_MIN_S, CHAT_MAX_S = 8, 20
CHAT_TITLE_CHARS = 80


def chat_answer_order(answer: dict, mode: str, language: str, show_at_s: int | None = None,
                      slot: str = CHAT_SLOT) -> dict:
    """A chat answer (a ``POST /api/ask`` response) as a ``chat_answer`` graphics order, for the producer.

    Deterministic: nothing is asked again, every field comes from the answer. Raises ValueError for an
    answer with ``status: error``, which has no text and is not a status a chat_answer order can carry.
    """
    if answer.get("status") == "error" or not answer.get("answer"):
        raise ValueError("an answer with status error has no text to show")
    at = min(answer["at_s"] if show_at_s is None else show_at_s, MAX_SHOW_AT_S)
    question = answer["question"].strip()
    title = question if len(question) <= CHAT_TITLE_CHARS else question[:CHAT_TITLE_CHARS - 1].rstrip() + "…"
    seconds = max(CHAT_MIN_S, min(CHAT_MAX_S, 4 + len(answer["answer"].split()) // 3))
    data = {k: answer[k] for k in ("question", "status", "tools") if k in answer}
    if answer.get("evidence"):
        data["evidence"] = list(answer["evidence"])
    key = f"{answer['match_id']}|{answer['at_s']}|{question}|{mode}|{language}|{answer['answer']}"
    return {
        "overlay_id": f"chat-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:10]}",
        "match_id": answer["match_id"],
        "source_insight": None,
        "period": 1 if at < 2700 else 2,
        "show_at": fmt_clock(at),
        "show_at_s": at,
        "duration_s": seconds,
        "slot": slot,
        "mode": mode,
        "language": language,
        "type": "chat_answer",
        "title": title,
        "text": answer["answer"],
        "data": data,
    }


def number(overlays: list[dict]) -> list[dict]:
    """Sort by time and give ids o001, o002, ... in that order."""
    order = {key: i for i, key in enumerate(VARIANT_KEYS)}
    ordered = sorted(overlays, key=lambda o: (o["show_at_s"], o["source_insight"] or "",
                                              order.get(f"{o['mode']}_{o['language']}", -1)))
    for i, overlay in enumerate(ordered, start=1):
        overlay["overlay_id"] = f"o{i:03d}"
    return ordered
