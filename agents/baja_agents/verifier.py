"""Verifier: a fact-checking agent that reads the four versions against the insight.

Code already checks numbers, stat labels and the scoreline. The verifier catches what
code cannot: a player put in the wrong team, an assist nobody gave, an equalizer
told as a lead. If it fails, the versions are kept: it can only reject, never block.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from .models import VARIANT_KEYS
from .narrator import DATA_NOTES

VERSION = "verifier-5"
INSTRUCTIONS = """
You are the fact-checker of Baja-Insights. You receive a football insight in JSON produced by a deterministic engine,
who is who (team and position of every player), the scoreline at that moment, and four on-screen versions of the
same graphic: fan_es, analyst_es, fan_en and analyst_en.

Go through the four versions one by one and list every factual claim: who did what, for which team, which number
goes with what, the scoreline and who is ahead, when it happened. For each claim decide `supported`:
- false if the data contradicts it: a player in the wrong team, a team credited with what the other team did,
  an action the data gives to someone else (an assist, a goal), a number attached to the wrong thing,
  a lead told as an equalizer, a time the clock does not support ("last minutes"), any prediction
- true if the data backs it, including fair readings: high possession can be "dominates" or "controls",
  a player far above the role can be "everywhere", an emotional adjective is not a claim

Every player in the versions comes tagged with the team, as "Mena [Bahía FC]". Check every tag against the team
the sentence credits: "Real Cardón wins the flank with Mena [Bahía FC]" is false.
`supported` is false only for a clear contradiction or an invented fact. Wording that is merely vague,
confusing or debatable is supported. `why` says, in a short English sentence, which data backs or contradicts it.
""" + DATA_NOTES


def tag_teams(text: str, who: dict) -> str:
    """'Mena gana' -> 'Mena [Bahía FC] gana', for every player in who_is_who (full name or surname)."""
    for name, info in sorted(who.items(), key=lambda item: -len(item[0])):
        surname = name.split(". ", 1)[-1]
        pattern = rf"(?<![\w.])(?:{re.escape(name)}|{re.escape(surname)})(?![\w])(?! \[)"
        text = re.sub(pattern, lambda m: f"{m.group(0)} [{info['team']}]", text)
    return text


class Claim(BaseModel):
    version: Literal["fan_es", "analyst_es", "fan_en", "analyst_en"]
    claim: str = Field(description="The claim, quoted from the version")
    supported: bool
    why: str


class Verdict(BaseModel):
    claims: list[Claim]


class Verifier:
    name = "verifier"

    def __init__(self, runner, agent=None, model: str = ""):
        self.runner = runner
        self.agent = agent
        self.version = f"{VERSION}:{model}" if model else VERSION  # the cache must not mix verifier models

    async def review(self, insight_view: dict, scoreline: str | None, texts: dict[str, dict]) -> dict[str, list[str]] | None:
        """Problems per version, or None if the verifier could not run."""
        who = insight_view.get("who_is_who", {})
        versions = {k: {"title": tag_teams(texts[k]["title"], who), "text": tag_teams(texts[k]["text"], who)}
                    for k in VARIANT_KEYS}
        payload = {"insight": insight_view, "scoreline": scoreline, "versions": versions}
        verdict = await self.runner.run(self.agent, self.name, self.version, payload, Verdict)
        if verdict is None:
            return None
        found: dict[str, list[str]] = {}
        for claim in verdict.claims:
            if not claim.supported:
                found.setdefault(claim.version, []).append(f"fact check: '{claim.claim}' {claim.why}")
        return found
