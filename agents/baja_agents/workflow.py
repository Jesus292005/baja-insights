"""Multi-agent orchestration with Microsoft Agent Framework.

One workflow run per block of play:

    Block ──▶ curator ──▶ narrator ──▶ personalizer ──▶ composer ──▶ overlays

The executors share a ``MatchContext``: scoreline, what was already shown and the
match summary once it exists. The curator reads it to avoid repeats, the narrator
to connect each moment with the story so far, and the composer writes it.
"""

# No ``from __future__ import annotations`` here: Agent Framework reads the handler
# type hints at runtime to route messages between executors.

import asyncio
from dataclasses import dataclass, field

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler
from baja_insights.contract import fmt_clock
from baja_insights.roster import Roster

from . import overlays
from .curator import MUST_SHOW, Curator, first_duel_of_half
from .models import Story
from .narrator import Narrator
from .personalizer import Personalized, Personalizer


@dataclass
class MatchContext:
    match_id: str
    home: str
    away: str
    goals: list = field(default_factory=list)       # (t_s, scoreline) of every goal seen
    summary: dict | None = None                     # match_summary facts, at full time
    history: list = field(default_factory=list)     # graphics already shown
    decisions: list = field(default_factory=list)   # curator log
    texts: list = field(default_factory=list)       # who wrote each graphic: agent or template
    unscheduled: list = field(default_factory=list)

    def scoreline_at(self, t_s: int) -> dict:
        score = {"home": 0, "away": 0}
        for goal_t, scoreline in self.goals:
            if goal_t <= t_s:
                score = scoreline
        return score

    def for_narrator(self, insight: dict) -> dict:
        context = {
            "clock": fmt_clock(insight["t_s"]),
            "home": self.home,
            "away": self.away,
            "scoreline": self.scoreline_at(insight["t_s"]),
            "recently_shown": [f"{fmt_clock(h['t_s'])} {h['title']}" for h in self.history[-6:]],
        }
        if insight["type"] == "top3" and self.summary:
            context["match_summary"] = self.summary
        return context


@dataclass
class Block:
    label: str
    insights: list


@dataclass
class Chosen:
    insights: list


@dataclass
class Narrated:
    items: list  # (insight, Story | None)


@dataclass
class Written:
    items: list  # (insight, Personalized)


class CuratorStep(Executor):
    def __init__(self, curator: Curator, context: MatchContext):
        super().__init__(id="curator")
        self.curator = curator
        self.context = context

    @handler
    async def run(self, block: Block, ctx: WorkflowContext[Chosen]) -> None:
        for insight in block.insights:
            if insight["type"] == "goal_chain":
                self.context.goals.append((insight["t_s"], insight["facts"]["scoreline"]))
            elif insight["type"] == "match_summary":
                self.context.summary = insight["facts"]
        selection = await self.curator.decide(block.label, block.insights, self.context.history)
        self.context.decisions.extend({"block": block.label, **d} for d in selection.decisions)
        await ctx.send_message(Chosen(selection.chosen))


class NarratorStep(Executor):
    def __init__(self, narrator: Narrator, context: MatchContext):
        super().__init__(id="narrator")
        self.narrator = narrator
        self.context = context

    @handler
    async def run(self, chosen: Chosen, ctx: WorkflowContext[Narrated]) -> None:
        stories = await asyncio.gather(*(self.narrator.explain(i, self.context.for_narrator(i)) for i in chosen.insights))
        await ctx.send_message(Narrated(list(zip(chosen.insights, stories))))


class PersonalizerStep(Executor):
    def __init__(self, personalizer: Personalizer, context: MatchContext):
        super().__init__(id="personalizer")
        self.personalizer = personalizer
        self.context = context

    @handler
    async def run(self, narrated: Narrated, ctx: WorkflowContext[Written]) -> None:
        written = await asyncio.gather(*(self.personalizer.adapt(i, s, self.context.scoreline_at(i["t_s"]))
                                         for i, s in narrated.items))
        await ctx.send_message(Written([(i, w) for (i, _), w in zip(narrated.items, written)]))


class ComposerStep(Executor):
    """Deterministic: places each graphic in time and slot and copies the numbers from the insight."""

    def __init__(self, context: MatchContext, roster: Roster):
        super().__init__(id="composer")
        self.context = context
        self.roster = roster
        self.scheduler = overlays.Scheduler()

    @handler
    async def run(self, written: Written, ctx: WorkflowContext[None, list]) -> None:
        out = []
        for insight, result in sorted(written.items, key=lambda item: item[0]["t_s"]):
            result: Personalized
            must_show = insight["type"] in MUST_SHOW or first_duel_of_half(insight, self.context.history)
            show_at = self.scheduler.place(insight, must_show=must_show)
            if show_at is None:
                self.context.unscheduled.append({"insight_id": insight["insight_id"], "reason": "su espacio en pantalla seguía ocupado"})
                continue
            out.extend(overlays.build(insight, result.texts, show_at, self.roster))
            self.context.history.append({"t_s": insight["t_s"], "period": insight["period"], "insight_type": insight["type"],
                                         "players": insight["players"], "team": insight["team"],
                                         "title": result.texts["fan_es"]["title"]})
            self.context.texts.append({"insight_id": insight["insight_id"], "sources": result.sources,
                                       "problems": result.problems})
        await ctx.yield_output(out)


def build_workflow(curator: Curator, narrator: Narrator, personalizer: Personalizer,
                   context: MatchContext, roster: Roster):
    steps = [CuratorStep(curator, context), NarratorStep(narrator, context),
             PersonalizerStep(personalizer, context), ComposerStep(context, roster)]
    return WorkflowBuilder(name="baja-insights-overlays", start_executor=steps[0]).add_chain(steps).build()
