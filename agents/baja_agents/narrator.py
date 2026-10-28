"""Narrator: explains why the chosen insight matters, in the context of the match so far."""

from __future__ import annotations

import json

from baja_insights.contract import fmt_clock
from baja_insights.roster import Roster

from .checks import without_ui_only
from .fallback import readable_stats
from .models import Story

VERSION = "narrator-5"
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
- A goal_chain with `penalty` was scored from the spot: `penalty.fouled` drew the foul, `penalty.fouled_by`
  committed it. Say it was a penalty ("de penal", "from the spot").
- `invisible_assist` is a run without the ball that dragged a defender and opened the space. When `touched_ball`
  is true the player also touched the ball earlier in the move: never say they did not touch it.
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


def penalty_of(chain: list[dict], events: list[dict]) -> dict | None:
    """Who drew and who gave away the penalty, when the goal's shot was one (``set_piece: "penalty"`` on the
    shot event). The chain does not say it: it only has the shot, and the foul is not a link."""
    shots = [link for link in chain if link.get("type") == "shot"]
    if not shots:
        return None
    by_id = {e["event_id"]: e for e in events}
    shot = by_id.get(shots[-1]["event_id"])
    if not shot or shot.get("set_piece") != "penalty":
        return None
    fouls = [e for e in events if e["type"] == "foul" and e["t_s"] <= shot["t_s"] and e["team"] != shot["team"]]
    foul = fouls[-1] if fouls else {}
    return {"fouled": foul.get("fouled") or shot["player"], "fouled_by": foul.get("player")}


def with_penalty(insight: dict, events: list[dict] | None) -> dict:
    """A goal_chain insight with ``facts.penalty`` when it was scored from the spot. The graphics orders never
    copy it (overlays.data_for picks its fields), so the contract does not change."""
    if insight["type"] != "goal_chain" or not events:
        return insight
    penalty = penalty_of(insight["facts"]["chain"], events)
    return {**insight, "facts": {**insight["facts"], "penalty": penalty}} if penalty else insight


def who_is_who(insight: dict, roster: Roster) -> dict:
    """Team and position of every player named anywhere in the insight."""
    facts = without_ui_only(insight["facts"])
    text = json.dumps(facts, ensure_ascii=False) + " ".join(insight["players"])
    return {p.name: {"team": p.team, "position": p.position}
            for p in roster.players.values() if p.name in text}


def slim(insight: dict, roster: Roster | None = None) -> dict:
    """The parts of an insight the agents need, without the evidence list, with the stats already worded."""
    facts = without_ui_only(insight["facts"])
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
