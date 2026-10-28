"""Checks on generated text: no invented numbers, short titles and texts."""

from __future__ import annotations

import json
import re

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
MAX_TITLE_WORDS = 6
MAX_TEXT_WORDS = 30
MAX_TEXT_WORDS_LONG = 40  # top3 and match_keys
LONG_TYPES = ("top3", "match_keys")
MAX_FAN_FIGURES = 1
PENALTY = re.compile(r"penal|penalty|from the spot", re.IGNORECASE)  # penal, penalti, penalty

# Facts copied to the overlay for the UI that the agents don't need: other players' MVP scores and the
# pitch coordinates of the goal chain. They are dropped at any depth, so they stay out of the prompts,
# which keeps the cache valid, and out of the numbers a text may use ("92" is not allowed because it
# happens to be a coordinate).
UI_ONLY_FACTS = ("ranking", "start", "end", "dragged_defender_start", "dragged_defender_end")
# Ids are numbers no text should show: "i03", event 190, evidence [24, 175].
EVENT_ID_KEYS = ("event_id", "trigger_event_id", "led_to_event_id", "key_events")
SCORELINE = re.compile(r"(?<![:\d])(?<!\d\.)(\d+)\s*-\s*(\d+)(?![:\d%])(?!\.\d)")  # 1-1, not 01:00-11:00 or 0.44-0.88

# "<number> <stat>" must carry the value of that stat (or of its family, e.g. recoveries in the opposition half)
STAT_WORDS = {
    ("key_passes",): r"pases? clave|key pass(?:es)?",
    ("progressive_passes",): r"pases? progresivos?|progressive pass(?:es)?",
    ("line_breaking_passes",): r"pases? que rompen? l[ií]neas|line-breaking pass(?:es)?",
    ("recoveries", "recoveries_opp_half"): r"recuperaci(?:ón|on|ones)|recover(?:y|ies)",
    ("duels_won", "duels_total"): r"duelos?|duels?",
    ("assists",): r"asistencias?|assists?",
}


# Markdown in chat answers: list markers ("1. ", "- "), headings, quotes, emphasis and inline code.
MD_BLOCK = re.compile(r"^[ \t]*(?:#{1,6}[ \t]+|>[ \t]?|[-*+][ \t]+|\d+[.)][ \t]+)", re.MULTILINE)
MD_INLINE = re.compile(r"(\*\*|__|\*|`|~~)(?=\S)(.+?)(?<=\S)\1")


def plain_text(markdown: str) -> str:
    """``markdown`` without its markup, so "1. Cota" counts no figure and the stage shows no asterisks.
    Underscore italics are left alone: they would break names like ``player_a``."""
    text = MD_BLOCK.sub("", markdown or "")
    for _ in range(2):  # **bold with *italic* inside**
        text = MD_INLINE.sub(r"\2", text)
    return text


INLINE_BULLET = re.compile(r"(?<!\d)[ \t]+-[ \t]+(?!\d)")  # " - Defenders", not the "0 - 1" of a scoreline


def tidy_markdown(markdown: str) -> str:
    """Puts on their own lines the bullets the model sometimes writes in a row ("line-up: - Goalkeeper: Arce -
    Defenders: ..."), which Markdown would show as one paragraph. Only lines with two or more of them that are
    not a bullet already, so "- Defensas: Mena - Quiroz" stays as it is."""
    lines = []
    for line in (markdown or "").strip().split("\n"):
        parts = INLINE_BULLET.split(line)
        if len(parts) < 3 or line.lstrip().startswith(("- ", "* ")):
            lines.append(line)
            continue
        head, items = parts[0].rstrip(), parts[1:]
        lines.extend(([head] if head else []) + [f"- {item.strip()}" for item in items if item.strip()])
    return "\n".join(lines)


def numbers(text: str) -> set[float]:
    return {float(n.replace(",", ".")) for n in NUMBER.findall(text or "")}


def _without_ids(value):
    if isinstance(value, dict):
        return {k: _without_ids(v) for k, v in value.items() if k not in UI_ONLY_FACTS and k not in EVENT_ID_KEYS}
    if isinstance(value, list):
        return [_without_ids(v) for v in value]
    return value


# Inside a goal chain link, the dragged defender is for drawing the run too. The agents already get it
# from invisible_assist, and keeping it out leaves their prompts as they were before the coordinates.
CHAIN_LINK_UI_ONLY = ("dragged_defender",)


def without_ui_only(value, in_chain: bool = False):
    """``value`` without the UI-only facts, at any depth (the coordinates live inside the goal chain)."""
    if isinstance(value, dict):
        drop = UI_ONLY_FACTS + (CHAIN_LINK_UI_ONLY if in_chain else ())
        return {k: without_ui_only(v, k == "chain") for k, v in value.items() if k not in drop}
    if isinstance(value, list):
        return [without_ui_only(v, in_chain) for v in value]
    return value


def content(insight: dict) -> dict:
    """The insight without what never belongs in a text: UI-only facts, its id, its evidence and event ids.

    Only the top-level ``evidence`` is a list of event ids. Inside match_keys, ``evidence`` is worded data.
    """
    return _without_ids({k: v for k, v in insight.items() if k not in ("insight_id", "evidence")})


def allowed_numbers(insight: dict, extra: dict | None = None) -> set[float]:
    """Every number of the insight's content (and of ``extra``, e.g. the scoreline), plus ratios as percentages."""
    base = numbers(json.dumps([content(insight), extra or {}], ensure_ascii=False))
    percents = {float(round(n * 100)) for n in base if 0 < n <= 1}
    return base | percents


def mislabeled_stats(insight: dict, text: str) -> list[str]:
    stats = insight["facts"].get("stats")
    if not stats:
        return []
    found = []
    for keys, words in STAT_WORDS.items():
        values = {float(stats[k]) for k in keys if k in stats}
        if not values:
            continue
        for match in re.finditer(rf"(\d+(?:[.,]\d+)?)\s+(?:{words})\b", text, flags=re.IGNORECASE):
            if float(match.group(1).replace(",", ".")) not in values:
                truth = ", ".join(f"{k} = {stats[k]}" for k in keys if k in stats)
                found.append(f"'{match.group(0)}' does not match the insight ({truth})")
    return found


def figures(text: str) -> int:
    """How many figures a text shows, not counting scorelines like 1-1."""
    return len(NUMBER.findall(SCORELINE.sub(" ", text or "")))


def valid_scorelines(insight: dict, scoreline: dict | None = None) -> set[str]:
    facts = insight["facts"]
    found = [scoreline, facts.get("scoreline"), facts.get("final_scoreline")]
    return {f"{s['home']}-{s['away']}" for s in found if s}


def wrong_scorelines(text: str, valid: set[str]) -> list[str]:
    """A scoreline written backwards ("1-0" when it is 0-1). Only that: "3-1" in duels is not a scoreline,
    and any other N-M pair is already checked as numbers."""
    if not valid:
        return []
    written = {f"{a}-{b}" for a, b in SCORELINE.findall(text or "")}
    backwards = {s for s in written - valid if "-".join(reversed(s.split("-"))) in valid}
    return [f"scoreline {s} is wrong, write it home-away as {' or '.join(sorted(valid))}" for s in sorted(backwards)]


def check_variant(insight: dict, title: str, text: str, allowed: set[float] | None = None,
                  mode: str = "", scoreline: dict | None = None) -> list[str]:
    """Problems with one title + text, as short sentences the model can act on. Empty means OK."""
    allowed = allowed if allowed is not None else allowed_numbers(insight, {"scoreline": scoreline})
    problems = []
    invented = sorted(numbers(f"{title} {text}") - allowed)
    if invented:
        problems.append(f"numbers not in the insight: {invented}")
    problems.extend(mislabeled_stats(insight, f"{title}. {text}"))
    problems.extend(wrong_scorelines(f"{title}. {text}", valid_scorelines(insight, scoreline)))
    if mode == "fan" and figures(text) > MAX_FAN_FIGURES:
        problems.append(f"fan text shows {figures(text)} figures, the limit is {MAX_FAN_FIGURES} besides the scoreline")
    if len(title.split()) > MAX_TITLE_WORDS:
        problems.append(f"title has more than {MAX_TITLE_WORDS} words")
    limit = MAX_TEXT_WORDS_LONG if insight["type"] in LONG_TYPES else MAX_TEXT_WORDS
    if len(text.split()) > limit:
        problems.append(f"text has more than {limit} words")
    if not title.strip() or not text.strip():
        problems.append("empty title or text")
    if insight["facts"].get("penalty") and not PENALTY.search(f"{title} {text}"):
        problems.append("this goal was a penalty: say so (de penal, penalty, from the spot)")
    return problems
