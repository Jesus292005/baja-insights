"""Runs a whole match, or block by block when live, and reports what each agent did."""

from __future__ import annotations

import asyncio
import logging
from itertools import groupby

from baja_insights.contract import fmt_clock
from baja_insights.roster import Roster

from . import config, curator, narrator, personalizer, verifier
from .llm import LLMRunner
from .narrator import score_text, slim
from .overlays import duel_frames, number
from .workflow import Block, MatchContext, build_workflow

log = logging.getLogger(__name__)


class Crew:
    """The three agents, their shared context and the workflow that connects them."""

    def __init__(self, roster: Roster, match_id: str, settings: config.Settings | None = None,
                 offline: bool = False, client=None, query=None):
        """``query`` is an engine ``MatchQuery`` over the match events; without it there are no duel bar frames."""
        self.query = query
        self.frames = 0
        self.settings = settings or config.Settings()
        self.roster = roster
        model = "" if offline else config.model_name()
        self.runner = LLMRunner(max_calls=self.settings.max_calls, timeout_s=self.settings.timeout_s,
                                concurrency=self.settings.concurrency, cache_dir=self.settings.cache_dir,
                                model=model, offline=offline)
        modules = {"curator": curator, "narrator": narrator, "personalizer": personalizer, "verifier": verifier}
        agents = dict.fromkeys(modules)
        if not offline:
            client = client or config.make_client()
            agents = {name: config.make_agent(client, name, module.INSTRUCTIONS) for name, module in modules.items()}
            if config.verifier_model_name() != config.model_name():
                agents["verifier"] = config.make_agent(config.make_client(config.verifier_model_name()), "verifier",
                                                       verifier.INSTRUCTIONS)
        self.context = MatchContext(match_id=match_id, home=roster.home, away=roster.away)
        self.verifier = verifier.Verifier(self.runner, agents["verifier"], "" if offline else config.verifier_model_name())
        self.workflow = build_workflow(
            curator.Curator(self.runner, agents["curator"]),
            narrator.Narrator(self.runner, agents["narrator"], roster),
            personalizer.Personalizer(self.runner, agents["personalizer"], home=roster.home, roster=roster,
                                      verifier=self.verifier),
            self.context, roster,
        )

    async def process_block(self, label: str, insights: list[dict]) -> list[dict]:
        """One block of play in, its overlays out (without ids yet). Usable live."""
        result = await self.workflow.run(Block(label, insights))
        return [overlay for batch in result.get_outputs() for overlay in batch]

    async def run_match(self, insights: list[dict]) -> tuple[list[dict], dict]:
        block_s = self.settings.block_s
        ordered = sorted(insights, key=lambda i: (i["t_s"], i["insight_id"]))
        out: list[dict] = []
        for index, group in groupby(ordered, key=lambda i: i["t_s"] // block_s if i["t_s"] < 5400 else 999):
            group = list(group)
            label = "final" if index == 999 else f"{fmt_clock(index * block_s)}-{fmt_clock((index + 1) * block_s)}"
            out.extend(await self.process_block(label, group))
        if self.query is not None:
            frames = duel_frames(out, lambda a, b, t: self.query.get_duel(a, b, fmt_clock(t)), self.context.match_id)
            self.frames = len(frames)
            out.extend(frames)
        return number(out), self.report()

    async def audit(self, overlays: list[dict], insights: list[dict]) -> list[dict]:
        """Run the verifier over graphics already generated. Returns one entry per graphic with problems."""
        by_id = {i["insight_id"]: i for i in insights}
        for insight in insights:
            if insight["type"] == "goal_chain":
                self.context.goals.append((insight["t_s"], insight["facts"]["scoreline"]))
        groups: dict[str, dict] = {}
        for overlay in overlays:
            if overlay["source_insight"]:
                groups.setdefault(overlay["source_insight"], {})[f"{overlay['mode']}_{overlay['language']}"] = {
                    "title": overlay["title"], "text": overlay["text"]}

        async def one(iid: str, texts: dict) -> dict | None:
            insight = by_id[iid]
            found = await self.verifier.review(slim(insight, self.roster),
                                               score_text(self.context.scoreline_at(insight["t_s"]), self.roster), texts)
            if found:
                return {"insight_id": iid, "clock": fmt_clock(insight["t_s"]), "problems": found,
                        "texts": {k: texts[k] for k in found}}
            return None

        results = await asyncio.gather(*(one(iid, texts) for iid, texts in groups.items()))
        return [r for r in results if r]

    def report(self) -> dict:
        texts = self.context.texts
        versions = [s for t in texts for s in t["sources"].values()]
        return {
            "match_id": self.context.match_id,
            "model_calls": self.runner.stats.as_dict(),
            "graphics": len(texts),
            "versions_by_agent": versions.count("agent"),
            "versions_by_template": versions.count("fallback"),
            "curator": self.context.decisions,
            "texts": texts,
            "unscheduled": self.context.unscheduled,
            "duel_frames": self.frames,
        }
