"""Curator: decides which insights of a block go on screen.

Hard rules live in code: goals, match keys and the top 3 always show, repeats are
dropped, and no block shows more than ``MAX_PER_BLOCK`` optional graphics. The
model only chooses among the remaining candidates, and if it fails the highest
priorities win.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from baja_insights.contract import fmt_clock

from .models import CuratorDecision

MUST_SHOW = ("goal_chain", "match_keys", "top3")
NO_OVERLAY = ("match_summary",)  # context for the narrator and the chat, not a graphic
MIN_PRIORITY = 0.4
MAX_PER_BLOCK = 3
COOLDOWN_S = 240  # same type about the same player within 4 minutes is a repeat

VERSION = "curator-1"
INSTRUCTIONS = """
You are the curator of Baja-Insights, a live football broadcast graphics system.
Every few minutes you receive the candidate insights of the last block of play and the graphics already shown.
Decide which candidates go on screen now.

Rules
- Show at most `budget` candidates. Showing fewer is fine if the rest add nothing.
- Prefer what changes the story of the match: a new MVP leader, a duel that flips, a player far above their role.
- Avoid saturating the screen with the same player or the same kind of graphic shown recently.
- Mix kinds of graphics when the priorities are close.
- Every candidate goes in `show` or in `drop`, with a one-sentence reason in Spanish.
- Use only the insight_id values you received.
"""


@dataclass
class Selection:
    chosen: list[dict]
    decisions: list[dict] = field(default_factory=list)


def _shares_player(a: dict, shown: dict) -> bool:
    return bool(set(a["players"]) & set(shown["players"]))


def is_repeat(insight: dict, history: list[dict]) -> bool:
    for shown in history:
        if insight["t_s"] - shown["t_s"] > COOLDOWN_S or shown["insight_type"] != insight["type"]:
            continue
        if insight["type"] == "duel_state":
            if set(shown["players"]) == set(insight["players"]) and not insight["facts"]["flipped"]:
                return True
        elif insight["type"] == "team_phase":
            if shown.get("team") == insight["team"]:
                return True
        elif _shares_player(insight, shown):
            return True
    return False


class Curator:
    name = "curator"

    def __init__(self, runner, agent=None):
        self.runner = runner
        self.agent = agent

    def triage(self, insights: list[dict], history: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
        """Split a block into (must show, candidates for the model, decisions already taken by rule)."""
        must, candidates, decided = [], [], []
        for insight in insights:
            iid = insight["insight_id"]
            if insight["type"] in NO_OVERLAY:
                decided.append({"insight_id": iid, "show": False, "by": "rule", "reason": "no tiene gráfico, sirve de contexto"})
            elif insight["type"] in MUST_SHOW:
                must.append(insight)
                decided.append({"insight_id": iid, "show": True, "by": "rule", "reason": "siempre se muestra"})
            elif insight["priority"] < MIN_PRIORITY:
                decided.append({"insight_id": iid, "show": False, "by": "rule", "reason": "prioridad baja"})
            elif is_repeat(insight, history):
                decided.append({"insight_id": iid, "show": False, "by": "rule", "reason": "repetido, ya se mostró hace poco"})
            else:
                candidates.append(insight)
        return must, candidates, decided

    def by_priority(self, candidates: list[dict]) -> list[dict]:
        """Highest priorities first, one graphic per player in the block, up to the budget."""
        chosen, players = [], set()
        for insight in sorted(candidates, key=lambda i: (-i["priority"], i["t_s"])):
            if players & set(insight["players"]):
                continue
            chosen.append(insight)
            players |= set(insight["players"])
            if len(chosen) == MAX_PER_BLOCK:
                break
        return chosen

    async def decide(self, block: str, insights: list[dict], history: list[dict]) -> Selection:
        must, candidates, decisions = self.triage(insights, history)
        chosen_ids: set[str] = set()
        picked_ids: set[str] = set()
        reasons: dict[str, str] = {}
        by = "rule"

        if len(candidates) >= 2:
            payload = {
                "block": block,
                "budget": MAX_PER_BLOCK,
                "candidates": [{"insight_id": i["insight_id"], "type": i["type"], "clock": fmt_clock(i["t_s"]),
                                "priority": i["priority"], "players": i["players"], "team": i["team"],
                                "facts": i["facts"]} for i in candidates],
                "recently_shown": [{"clock": fmt_clock(h["t_s"]), "type": h["insight_type"], "players": h["players"],
                                    "title": h["title"]} for h in history[-8:]],
            }
            decision = await self.runner.run(self.agent, self.name, VERSION, payload, CuratorDecision)
            if decision is not None:
                by = "agent"
                valid = {i["insight_id"] for i in candidates}
                picked_ids = {p.insight_id for p in decision.show if p.insight_id in valid}
                ranked = self.by_priority([i for i in candidates if i["insight_id"] in picked_ids])
                chosen_ids = {i["insight_id"] for i in ranked}
                reasons = {p.insight_id: p.reason for p in [*decision.show, *decision.drop] if p.insight_id in valid}

        if by == "rule":
            chosen_ids = {i["insight_id"] for i in self.by_priority(candidates)}

        for insight in candidates:
            iid = insight["insight_id"]
            shown = iid in chosen_ids
            if by == "agent" and iid in picked_ids and not shown:
                reason = "fuera del cupo del bloque"
            else:
                reason = reasons.get(iid, "elegido por prioridad" if shown else "fuera del cupo del bloque")
            decisions.append({"insight_id": iid, "show": shown, "by": by, "reason": reason})

        chosen = [i for i in insights if i in must or i["insight_id"] in chosen_ids]
        return Selection(chosen=chosen, decisions=decisions)
