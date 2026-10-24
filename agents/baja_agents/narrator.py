"""Narrator: explains why the chosen insight matters, in the context of the match so far."""

from __future__ import annotations

import json

from baja_insights.contract import fmt_clock
from baja_insights.roster import Roster

from .checks import UI_ONLY_FACTS
from .fallback import readable_stats
from .models import Story

VERSION = "narrator-4"
INSTRUCTIONS = """
You are the narrator of Baja-Insights. You receive one football insight in JSON, produced by a deterministic engine,
and the context of the match so far. Explain why this moment matters.

Rules
- Use only the data in the insight and the context. Never invent figures, names, plays or causes.
- Explain why it matters for the match, not only what happened. Connect it to the context when it is relevant,
  for example the scoreline or a player who was already on screen.
- Never predict the outcome or give probabilities of winning.
- `key_facts` lists the facts you rely on, copied with the same numbers as in the insight.
- When you mention a stat, copy its wording from `stats_worded`. Never move a number to another stat:
  progressive passes are not key passes, and `expected_for_role` values are expectations, not what the player did.
- Never give a player, a duel or an action to the wrong team.
- Write in Spanish. Keep it short: the angle in a few words, why_it_matters in one or two sentences.
"""


DATA_NOTES = """
How to read the data
- Values per team are keyed by the team name, for example "pass_accuracy_pct": {"Bahía FC": 66, "Real Cardón": 91}.
- Scorelines come as text with the home team first, "Bahía FC 0-1 Real Cardón". Write them in that order: 0-1.
- `who_is_who` gives the team and position of every player named in the insight.
"""


def score_text(scoreline: dict | None, roster: Roster | None) -> str | dict | None:
    if not scoreline or roster is None:
        return scoreline
    return f"{roster.home} {scoreline['home']}-{scoreline['away']} {roster.away}"


def name_sides(value, roster: Roster):
    """Replace home/away keys by team names, and scorelines by text, so no agent has to map sides."""
    if isinstance(value, list):
        return [name_sides(v, roster) for v in value]
    if not isinstance(value, dict):
        return value
    if value and set(value) <= {"home", "away"}:
        return {roster.home if k == "home" else roster.away: name_sides(v, roster) for k, v in value.items()}
    return {k: score_text(v, roster) if k in ("scoreline", "final_scoreline") else name_sides(v, roster)
            for k, v in value.items()}
INSTRUCTIONS += DATA_NOTES


def who_is_who(insight: dict, roster: Roster) -> dict:
    """Team and position of every player named anywhere in the insight."""
    facts = {k: v for k, v in insight["facts"].items() if k not in UI_ONLY_FACTS}
    text = json.dumps(facts, ensure_ascii=False) + " ".join(insight["players"])
    return {p.name: {"team": p.team, "position": p.position}
            for p in roster.players.values() if p.name in text}


def slim(insight: dict, roster: Roster | None = None) -> dict:
    """The parts of an insight the agents need, without the evidence list, with the stats already worded."""
    facts = {k: v for k, v in insight["facts"].items() if k not in UI_ONLY_FACTS}
    out = {"insight_id": insight["insight_id"], "type": insight["type"], "clock": fmt_clock(insight["t_s"]),
           "period": insight["period"], "players": insight["players"], "team": insight["team"],
           "facts": facts}
    if insight["facts"].get("stats"):
        out["stats_worded"] = readable_stats(insight["facts"]["stats"])
    if roster is not None:
        out["facts"] = name_sides(facts, roster)
        out["home_team"], out["away_team"] = roster.home, roster.away
        out["who_is_who"] = who_is_who(insight, roster)
    return out


class Narrator:
    name = "narrator"

    def __init__(self, runner, agent=None, roster: Roster | None = None):
        self.runner = runner
        self.agent = agent
        self.roster = roster

    async def explain(self, insight: dict, context: dict) -> Story | None:
        context = {**context, "scoreline": score_text(context.get("scoreline"), self.roster)}
        payload = {"insight": slim(insight, self.roster), "context": context}
        return await self.runner.run(self.agent, self.name, VERSION, payload, Story)
