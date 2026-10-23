"""Structured outputs the agents must return (sent as ``response_format``)."""

from __future__ import annotations

from pydantic import BaseModel, Field

VARIANT_KEYS = ("fan_es", "analyst_es", "fan_en", "analyst_en")


class Pick(BaseModel):
    insight_id: str
    reason: str = Field(description="One short sentence in Spanish")


class CuratorDecision(BaseModel):
    show: list[Pick]
    drop: list[Pick]


class Story(BaseModel):
    angle: str = Field(description="The story in a few words, in Spanish")
    why_it_matters: str = Field(description="Why this moment changes the match, one or two sentences in Spanish")
    key_facts: list[str] = Field(description="The facts from the insight that support it, copied as they are")


class Variant(BaseModel):
    title: str
    text: str


class Variants(BaseModel):
    fan_es: Variant
    analyst_es: Variant
    fan_en: Variant
    analyst_en: Variant
