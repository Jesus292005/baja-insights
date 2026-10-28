"""Personalization: four versions of each graphic, fan and analyst, in Spanish and English.

Every version is checked in code and then by the verifier agent. If one fails, the
model gets one retry with the problems listed. Each version keeps the latest attempt
that passed, and the ones that never passed are replaced by their template.
"""

from __future__ import annotations

from dataclasses import dataclass

from baja_insights.roster import Roster

from . import fallback
from .checks import allowed_numbers, check_variant
from .models import VARIANT_KEYS, Story, Variants
from .narrator import DATA_NOTES, score_text, slim
from .verifier import Verifier

VERSION = "personalizer-7"
INSTRUCTIONS = """
You are the personalization agent of Baja-Insights. You receive a football insight in JSON, the scoreline at that
moment and, when available, the narrator's story about why it matters. Write the on-screen title and text in four
versions: fan_es, analyst_es, fan_en and analyst_en.

Rules
- Only use data from the insight, the scoreline and the story. Never invent figures, names or plays.
- Every number you write must appear in the insight or the scoreline. Percentages may be written from ratios (0.38 -> 38%).
- When you mention a stat, copy its wording from `stats_worded`. Never move a number to another stat:
  progressive passes are not key passes, and `expected_for_role` values are expectations, not what the player did.
- fan is for a casual fan: tell the story with emotion. The fan text has at most ONE figure besides the
  scoreline, and no decimals. Prefer words ("doubled what is expected", "everywhere") to numbers.
- analyst is for an analyst: precise, with the key figures from the insight.
- Say when something happened only if the clock is in the data. Do not call a moment "the last minutes" or
  "the second half" unless the clock says so.
- Write player and team names exactly as in the insight, with accents and ñ.
- Never give a player, a duel or an action to the wrong team, and never give a player an action the data
  gives to someone else (an assist, a goal, a pass).
- For top3, the fan title answers who really won the match, beyond the scoreline.
- Title of at most 6 words. Text of at most 30 words, or 40 for top3 and match_keys.
- Write fan_es and analyst_es in Spanish, fan_en and analyst_en in English. Translate the facts, not word by word.
- Refer to players by surname. Do not use gendered pronouns for players.
- Never predict the outcome.
- If you receive `fix`, your previous answer broke those rules: rewrite only what is needed to fix it.
""" + DATA_NOTES


@dataclass
class Personalized:
    texts: dict[str, dict]
    sources: dict[str, str]   # 'agent' or 'fallback' per version
    problems: dict[str, list[str]]


class Personalizer:
    name = "personalizer"

    def __init__(self, runner, agent=None, home: str = "", roster: Roster | None = None,
                 verifier: Verifier | None = None):
        self.runner = runner
        self.agent = agent
        self.home = home
        self.roster = roster
        self.verifier = verifier

    async def _review(self, insight: dict, view: dict, variants: Variants, allowed: set[float],
                      scoreline: dict | None) -> dict[str, list[str]]:
        """Code checks first; the versions that pass them go to the fact-checker."""
        found = {}
        for key in VARIANT_KEYS:
            v = getattr(variants, key)
            issues = check_variant(insight, v.title, v.text, allowed, mode=key.split("_")[0], scoreline=scoreline)
            if issues:
                found[key] = issues
        if self.verifier and len(found) < len(VARIANT_KEYS):
            checked = await self.verifier.review(view, score_text(scoreline, self.roster), variants.model_dump())
            for key, issues in (checked or {}).items():
                found.setdefault(key, []).extend(issues)
        return found

    async def adapt(self, insight: dict, story: Story | None, scoreline: dict | None = None) -> Personalized:
        templates = fallback.variants(insight, self.home)
        allowed = allowed_numbers(insight, {"scoreline": scoreline})
        view = slim(insight, self.roster)
        payload = {"insight": view, "scoreline": score_text(scoreline, self.roster), "story": story.model_dump() if story else None}

        attempts: list[tuple[Variants, dict]] = []
        first = await self.runner.run(self.agent, self.name, VERSION, payload, Variants)
        if first is not None:
            problems = await self._review(insight, view, first, allowed, scoreline)
            attempts.append((first, problems))
            if problems:
                retry = {**payload, "previous": first.model_dump(), "fix": problems}
                second = await self.runner.run(self.agent, self.name, VERSION, retry, Variants)
                if second is not None:
                    attempts.insert(0, (second, await self._review(insight, view, second, allowed, scoreline)))

        texts, sources, remaining = {}, {}, {}
        for key in VARIANT_KEYS:
            good = next((v for v, p in attempts if key not in p), None)
            if good is not None:
                texts[key], sources[key] = getattr(good, key).model_dump(), "agent"
            else:
                texts[key], sources[key] = templates[key], "fallback"
                if attempts:
                    remaining[key] = attempts[0][1].get(key, [])
        return Personalized(texts=texts, sources=sources, problems=remaining)
