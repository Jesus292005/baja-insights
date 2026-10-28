"""Offline tests: fake agents stand in for Foundry, so no credentials or network are needed."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from baja_agents import fallback
from baja_agents.checks import check_variant
from baja_agents.config import Settings
from baja_agents.curator import MAX_PER_BLOCK, Curator
from baja_agents.llm import LLMRunner
from baja_agents.models import CuratorDecision, Variants
from baja_agents.narrator import with_penalty
from baja_agents.overlays import Scheduler
from baja_agents.personalizer import Personalizer
from baja_agents.pipeline import Crew
from baja_insights.cli import read_events
from baja_insights.roster import Roster

ROOT = Path(__file__).resolve().parents[2]
M001 = json.loads((ROOT / "data" / "m001" / "insights.json").read_text(encoding="utf-8"))
SAMPLE = json.loads((ROOT / "mocks" / "insights_sample.json").read_text(encoding="utf-8"))
ROSTER = Roster.load(ROOT / "mocks" / "teams.json")
F091_EVENTS = read_events(ROOT / "data" / "f091" / "events.jsonl")  # the match without a script, in the video
F091 = [with_penalty(i, F091_EVENTS)
        for i in json.loads((ROOT / "data" / "f091" / "insights.json").read_text(encoding="utf-8"))]


def by_id(insights, iid):
    return next(i for i in insights if i["insight_id"] == iid)


def find(insights, kind, **facts):
    """The first insight of ``kind`` whose facts match: each value is either equal or a test on the fact.

    m001's insight ids move every time the engine adds a moment, so the tests look insights up by what they say.
    """
    def matches(insight):
        return all(want(insight["facts"].get(k)) if callable(want) else insight["facts"].get(k) == want
                   for k, want in facts.items())
    return next(i for i in insights if i["type"] == kind and matches(i))


def surname(player):
    return player.split(". ", 1)[-1]


OPENER = find(M001, "goal_chain", scoreline={"home": 0, "away": 1})
EQUALISER = find(M001, "goal_chain", scoreline={"home": 1, "away": 1})  # Cota, Torres' run, Salgado, Ramírez
DRIBBLES = find(M001, "card_upgrade", reason_code="dribbles")  # count 2, written as a word in English


def scoreline_at(t_s):
    goals = [g for g in (OPENER, EQUALISER) if g["t_s"] <= t_s]
    return goals[-1]["facts"]["scoreline"] if goals else {"home": 0, "away": 0}


def between_the_goals(insight):
    return OPENER["t_s"] < insight["t_s"] < EQUALISER["t_s"]


class FakeAgent:
    """Answers with the given replies in order; an Exception reply is raised."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    async def run(self, prompt, options=None):
        self.prompts.append(json.loads(prompt))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(value=reply, text=reply.model_dump_json())


def runner(tmp_path=None, **kw):
    return LLMRunner(max_calls=kw.get("max_calls", 50), timeout_s=5, concurrency=2, cache_dir=tmp_path)


def good_variants(text="Torres sube al primer lugar."):
    v = {"title": "Torres manda", "text": text}
    return Variants(fan_es=v, analyst_es=v, fan_en=v, analyst_en=v)


@pytest.fixture(scope="module")
def jsonschema_validator():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((ROOT / "contracts" / "overlay.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


# --------------------------------------------------------------- templates
@pytest.mark.parametrize("insight", [i for i in M001 + SAMPLE + F091 if i["type"] != "match_summary"],
                         ids=lambda i: f"{i['match_id']}-{i['insight_id']}-{i['type']}")
def test_templates_pass_the_checks(insight):
    for key, v in fallback.variants(insight, ROSTER.home).items():
        assert check_variant(insight, v["title"], v["text"], mode=key.split("_")[0]) == [], key


def test_f091_penalty_and_the_run_that_touched_the_ball():
    penalties = [i for i in F091 if i["facts"].get("penalty")]
    assert [(i["facts"]["scorer"], i["facts"]["penalty"]) for i in penalties] == [
        ("C. Ibarra", {"fouled": "C. Ibarra", "fouled_by": "J. Castro"})]
    v = fallback.variants(penalties[0], ROSTER.home)
    assert v["fan_es"] == {"title": "Gol de penal de Ibarra", "text": "Ibarra lo cobra desde el punto penal. 2-2."}
    assert v["analyst_en"]["text"].startswith("Castro fouls Ibarra in the box")
    # Salgado's run dragged Meza for the 1-2, but Salgado had touched the ball earlier in the move
    run = find(F091, "goal_chain", scoreline={"home": 1, "away": 2})
    assert run["facts"]["invisible_assist"]["touched_ball"] is True
    texts = " ".join(t["text"] for t in fallback.variants(run, ROSTER.home).values())
    assert "Salgado arrastró a Meza y abrió el espacio." in texts and "sin tocar" not in texts
    assert "without touching" not in texts


def test_fan_text_allows_one_figure_besides_the_scoreline():
    insight = find(M001, "standout_milestone", player="F. Cota")
    rec, prog = insight["facts"]["stats"]["recoveries"], insight["facts"]["stats"]["progressive_passes"]
    score = scoreline_at(insight["t_s"])
    text = f"Cota está en todas con {rec} recuperaciones en el {score['home']}-{score['away']}."
    assert check_variant(insight, "Cota", text, mode="fan", scoreline=score) == []
    two = f"Cota suma {rec} recuperaciones y {prog} pases progresivos."
    assert check_variant(insight, "Cota", two, mode="fan")
    assert check_variant(insight, "Cota", two, mode="analyst") == []


def test_english_templates_use_the_engine_codes():
    v = fallback.variants(EQUALISER, ROSTER.home)
    assert v["fan_en"]["text"].startswith("It starts with Cota's recovery")
    assert "Salgado (pass that broke 2 lines)" in v["analyst_en"]["text"]
    assert v["fan_es"]["text"].startswith("La jugada nace con una recuperación de Cota")
    who = surname(DRIBBLES["facts"]["player"])
    assert fallback.variants(DRIBBLES)["fan_en"]["text"] == f"{who}: two dribbles won in under 10 minutes."
    for code, params, text in [
        ("opp_half_recoveries", {"count": 3, "window_min": 10}, "third recovery in the opposition half in under 10 minutes"),
        ("run_opened_goal", {"dragged_defender": "G. Cárdenas", "dragged_position": "DFC"},
         "dragged the centre-back and opened the space for the goal"),
        ("run_ended_in_shot", {"dragged_defender": "E. Quiroz"}, "dragged E. Quiroz and the move ended in a shot"),
        ("line_breaking_pass", {"lines": 1, "under_pressure": False}, "pass that broke 1 line"),
        ("pass_streak", {"count": 20}, "20 passes in a row without a miss"),
        ("recovery_to_shot", {"seconds": 18, "shooter": "S. Leyva"},
         "won the ball in their own half and the team shot 18 seconds later"),
        ("big_save", {"xg": 0.3, "shooter": "M. Ramírez"}, "save from a shot worth 0.30 xG"),
    ]:
        assert fallback.card_reason_en({"reason_code": code, "reason_params": params}) == text


def test_english_templates_without_codes_keep_the_old_text():
    goal = EQUALISER
    old = {**goal, "facts": {**goal["facts"], "chain": [{k: v for k, v in link.items() if k not in ("type", "lines_broken", "cross")}
                                                       for link in goal["facts"]["chain"]]}}
    assert fallback.variants(old)["fan_en"]["text"].startswith("It starts with Cota and")
    card = DRIBBLES
    old_card = {**card, "facts": {k: v for k, v in card["facts"].items() if k not in ("reason_code", "reason_params")}}
    expected = f"{surname(card['facts']['player'])} earns +{card['facts']['delta']} Dribbling."
    assert fallback.variants(old_card)["fan_en"]["text"] == expected


def test_possession_spell_has_its_own_template():
    spell = find(M001, "team_phase", label="possession_spell")
    v = fallback.variants(spell, ROSTER.home)
    assert v["fan_es"]["text"] == f"{spell['team']} encadenó {spell['facts']['passes']} pases seguidos."
    assert v["analyst_en"]["title"] == "Long spell"
    assert "presión" not in v["fan_es"]["text"] and "press" not in v["fan_en"]["text"]


def test_check_flags_invented_numbers_and_long_titles():
    insight = by_id(SAMPLE, "i05")
    assert check_variant(insight, "Torres manda", "Torres lleva 6.2 puntos.") == []
    assert "numbers not in the insight" in check_variant(insight, "Torres", "Torres lleva 7 recuperaciones.")[0]
    assert check_variant(insight, "uno dos tres cuatro cinco seis siete", "texto")


def test_check_flags_numbers_moved_to_another_stat():
    cota = find(M001, "standout_milestone", player="F. Cota",
                stats=lambda s: s["progressive_passes"] != s["key_passes"])
    rec, prog = cota["facts"]["stats"]["recoveries"], cota["facts"]["stats"]["progressive_passes"]
    assert check_variant(cota, "Cota", f"Cota suma {rec} recuperaciones y {prog} pases progresivos.") == []
    problems = check_variant(cota, "Cota", f"Cota recuperó {rec} balones y dio {prog} pases clave.")
    assert problems and f"{prog} pases clave" in problems[0]


def test_check_flags_a_scoreline_written_backwards():
    insight = next(i for i in M001 if i["type"] == "mvp_rank_change" and between_the_goals(i))
    score = OPENER["facts"]["scoreline"]
    assert check_variant(insight, "Cardón", "Real Cardón gana 0-1.", scoreline=score) == []
    assert "scoreline 1-0" in check_variant(insight, "Cardón", "Real Cardón gana 1-0.", scoreline=score)[0]
    control = find(M001, "team_phase", label="control")
    text = f"{control['facts']['possession_pct']}% de posesión entre {control['facts']['window']}."
    assert check_variant(control, "Control", text) == []


def test_ranking_and_ids_are_not_numbers_a_text_may_use():
    from baja_agents.checks import allowed_numbers
    # a rise whose ranking holds a score that belongs only to another player
    mvp, other = next((i, r["mvp_score"]) for i in M001 if i["type"] == "mvp_rank_change"
                      for r in i["facts"]["ranking"] if float(r["mvp_score"]) not in allowed_numbers(i))
    who = surname(mvp["facts"]["player"])
    assert check_variant(mvp, who, f"{who} sube con {mvp['facts']['mvp_score']} puntos.") == []
    assert check_variant(mvp, who, f"{who} sube con {other} puntos.")
    trigger = mvp["facts"]["trigger_event_id"]
    assert check_variant(mvp, who, f"Jugada {mvp['evidence'][0]}.")
    assert check_variant(mvp, who, f"Jugada {trigger}.")
    keys = find(M001, "match_keys")  # its keys' `evidence` is worded data, not event ids
    evidence = keys["facts"]["keys"]["Bahía FC"][0]["evidence"]
    assert check_variant(keys, "Claves", f"Bahía FC: {evidence}.") == []


def test_curator_does_not_see_the_ranking():
    block = [i for i in M001 if 600 <= i["t_s"] < 900]
    agent = FakeAgent(CuratorDecision(show=[], drop=[]))
    asyncio.run(Curator(runner(), agent).decide("10:00-15:00", block, history=[]))
    assert all("ranking" not in c["facts"] for c in agent.prompts[0]["candidates"])


def test_chain_coordinates_reach_the_overlay_but_not_the_agents():
    from baja_agents.checks import without_ui_only
    from baja_agents.narrator import slim
    from baja_agents.overlays import build
    goal = EQUALISER  # Torres' run, dragging Cárdenas
    torres = next(link for link in goal["facts"]["chain"] if link["player"] == "J. Torres")
    assert torres["end"] and torres["dragged_defender_end"]
    # a number that only exists as a coordinate is invented in a text
    assert check_variant(goal, "Torres", f"Torres corrió hasta el metro {torres['end'][0]}.")
    # the overlay keeps the coordinates for the UI
    texts = {k: {"title": "t", "text": "x"} for k in ("fan_es", "analyst_es", "fan_en", "analyst_en")}
    detail = build(goal, texts, goal["t_s"] + 2, ROSTER)[0]["data"]["chain_detail"]
    assert next(link for link in detail if link["player"] == "J. Torres")["end"] == torres["end"]
    # the agents never see them, so their prompts (and the cache) are the same as before the engine change
    view = json.dumps(slim(goal, ROSTER))
    assert '"start"' not in view and '"end"' not in view and "dragged_defender_start" not in view
    assert slim(goal, ROSTER) == slim({**goal, "facts": without_ui_only(goal["facts"])}, ROSTER)
    # the dragged defender: out of the chain links (it is for drawing), still in invisible_assist (for the story)
    assert all("dragged_defender" not in link for link in slim(goal, ROSTER)["facts"]["chain"])
    assert slim(goal, ROSTER)["facts"]["invisible_assist"]["dragged_defender"] == "G. Cárdenas"
    assert next(link for link in detail if link["player"] == "J. Torres")["dragged_defender"] == "G. Cárdenas"


def test_scoreline_from_context_is_allowed():
    from baja_agents.checks import allowed_numbers
    # between the goals, with no 0 among its own numbers
    insight = next(i for i in M001 if i["type"] == "mvp_rank_change" and between_the_goals(i)
                   and 0.0 not in allowed_numbers(i))
    text = "Cardón sigue con el 0-1."
    assert check_variant(insight, "Cardón", text) != []
    assert check_variant(insight, "Cardón", text, allowed_numbers(insight, {"scoreline": {"home": 0, "away": 1}})) == []


# ----------------------------------------------------------------- curator
def test_curator_keeps_must_show_and_caps_the_model():
    block = [i for i in M001 if 3600 <= i["t_s"] < 3900]
    candidates_ids = [i["insight_id"] for i in block if i["type"] not in ("goal_chain",)]
    decision = CuratorDecision(show=[{"insight_id": iid, "reason": "sí"} for iid in candidates_ids + ["i999"]], drop=[])
    curator = Curator(runner(), FakeAgent(decision))
    selection = asyncio.run(curator.decide("60:00-65:00", block, history=[]))
    must = curator.triage(block, history=[])[0]  # the goal, and the half's first duel
    assert "goal_chain" in [i["type"] for i in must]
    assert all(i in selection.chosen for i in must)
    assert len([i for i in selection.chosen if i not in must]) <= MAX_PER_BLOCK
    assert all(d["insight_id"] != "i999" for d in selection.decisions)
    assert len(selection.decisions) == len(block)


def test_curator_falls_back_to_priority_when_the_model_fails():
    block = [i for i in M001 if 1500 <= i["t_s"] < 1800]
    curator = Curator(runner(), FakeAgent(RuntimeError("boom")))
    selection = asyncio.run(curator.decide("25:00-30:00", block, history=[]))
    assert selection.chosen
    assert all(d["by"] == "rule" for d in selection.decisions)


def test_curator_drops_repeats():
    duel = find(M001, "duel_state", player_a="D. Mena", player_b="D. Verdugo", flipped=False)
    history = [{"t_s": duel["t_s"] - 60, "period": duel["period"], "insight_type": "duel_state",
                "players": duel["players"], "team": None, "title": "x"}]
    _, candidates, decided = Curator(runner()).triage([duel], history)
    assert candidates == [] and decided[0]["reason"].startswith("repetido")


def test_the_first_duel_of_each_half_always_shows():
    # f091's duels all had low priority or lost to other graphics, so the match had no duel bar
    first, second = [next(i for i in F091 if i["type"] == "duel_state" and i["period"] == p) for p in (1, 2)]
    assert first["priority"] < 0.4
    later = next(i for i in F091 if i["type"] == "duel_state" and i["period"] == 1 and i is not first)
    must, _, decided = Curator(runner()).triage([first, later], history=[])
    assert must == [first] and decided[0]["reason"].startswith("primer duelo")
    shown = [{"t_s": first["t_s"], "period": 1, "insight_type": "duel_state", "players": first["players"],
              "team": None, "title": "x"}]
    assert Curator(runner()).triage([later], shown)[0] == []  # the half already has its duel
    assert Curator(runner()).triage([second], shown)[0] == [second]  # the second half gets its own


# ------------------------------------------------------------ personalizer
def test_personalizer_retries_then_uses_templates_for_what_still_fails():
    insight = by_id(SAMPLE, "i05")
    invented = good_variants("Torres lleva 99 recuperaciones.")
    agent = FakeAgent(invented, invented)
    result = asyncio.run(Personalizer(runner(), agent).adapt(insight, None))
    assert len(agent.prompts) == 2 and "fix" in agent.prompts[1]
    assert set(result.sources.values()) == {"fallback"}


def test_personalizer_keeps_good_versions():
    insight = by_id(SAMPLE, "i05")
    result = asyncio.run(Personalizer(runner(), FakeAgent(good_variants())).adapt(insight, None))
    assert set(result.sources.values()) == {"agent"}
    assert result.texts["fan_en"]["title"] == "Torres manda"


def test_verifier_rejection_triggers_a_retry_and_keeps_what_passed():
    from baja_agents.verifier import Verdict, Verifier
    insight = by_id(SAMPLE, "i05")
    first = good_variants("Torres sube al primer lugar.")
    second = good_variants("Torres ya es el número uno.")
    wrong = {"version": "fan_es", "claim": "Torres sube al primer lugar", "supported": False, "why": "wrong team"}
    ok = {"version": "fan_es", "claim": "Torres ya es el número uno", "supported": True, "why": "rank 1"}
    shared = runner()
    verifier = Verifier(shared, FakeAgent(Verdict(claims=[wrong]), Verdict(claims=[ok])))
    writer = FakeAgent(first, second)
    result = asyncio.run(Personalizer(shared, writer, roster=ROSTER, verifier=verifier).adapt(insight, None))
    assert "fact check" in writer.prompts[1]["fix"]["fan_es"][0]
    assert result.texts["fan_es"]["text"] == "Torres ya es el número uno."
    assert set(result.sources.values()) == {"agent"}


def test_verifier_failure_never_blocks():
    from baja_agents.verifier import Verifier
    verifier = Verifier(runner(), FakeAgent(RuntimeError("down")))
    result = asyncio.run(Personalizer(runner(), FakeAgent(good_variants()), roster=ROSTER, verifier=verifier)
                         .adapt(by_id(SAMPLE, "i05"), None))
    assert set(result.sources.values()) == {"agent"}


def test_team_tags_for_the_verifier():
    from baja_agents.verifier import tag_teams
    who = {"D. Mena": {"team": "Bahía FC"}, "D. Verdugo": {"team": "Real Cardón"}}
    assert tag_teams("Cardón gana con D. Mena y Verdugo.", who) == \
        "Cardón gana con D. Mena [Bahía FC] y Verdugo [Real Cardón]."


def test_agents_see_teams_instead_of_home_and_away():
    from baja_agents.narrator import slim
    keys = find(M001, "match_keys")
    view = slim(keys, ROSTER)
    pos, score = keys["facts"]["possession_pct"], keys["facts"]["scoreline"]
    assert view["facts"]["possession_pct"] == {"Bahía FC": pos["home"], "Real Cardón": pos["away"]}
    assert view["facts"]["scoreline"] == f"Bahía FC {score['home']}-{score['away']} Real Cardón"
    assert view["who_is_who"]["J. Torres"]["team"] == "Bahía FC"
    assert view["who_is_who"]["D. Verdugo"]["team"] == "Real Cardón"


def test_cache_avoids_a_second_call(tmp_path):
    insight = by_id(SAMPLE, "i05")
    shared = runner(tmp_path)
    asyncio.run(Personalizer(shared, FakeAgent(good_variants())).adapt(insight, None))
    again = asyncio.run(Personalizer(shared, FakeAgent()).adapt(insight, None))
    assert shared.stats.calls == 1 and shared.stats.cache_hits == 1
    assert set(again.sources.values()) == {"agent"}


def test_rate_limit_is_retried(monkeypatch):
    import baja_agents.llm as llm
    monkeypatch.setattr(llm, "RATE_LIMIT_WAITS_S", (0, 0))
    shared = runner()
    agent = FakeAgent(RuntimeError("Error code: 429 - rate_limit_exceeded"), good_variants())
    result = asyncio.run(Personalizer(shared, agent).adapt(by_id(SAMPLE, "i05"), None))
    assert shared.stats.rate_limited == 1 and shared.stats.failures == 0 and shared.stats.calls == 1
    assert set(result.sources.values()) == {"agent"}


def test_budget_stops_calls():
    shared = runner(max_calls=0)
    result = asyncio.run(Personalizer(shared, FakeAgent()).adapt(by_id(SAMPLE, "i05"), None))
    assert shared.stats.calls == 0 and shared.stats.skipped == 1
    assert set(result.sources.values()) == {"fallback"}


# --------------------------------------------------------------- schedule
def test_center_graphic_blocks_other_slots():
    scheduler = Scheduler()
    goal, card = by_id(SAMPLE, "i11"), by_id(SAMPLE, "i12")
    goal_at = scheduler.place(goal, must_show=True)
    card_at = scheduler.place({**card, "t_s": goal["t_s"]}, must_show=True)
    assert card_at >= goal_at + 10


def notice(at, bar, a="D. Mena", b="D. Verdugo", slot="bottom_bar", kind="duel_bar"):
    return {"source_insight": f"i{at}", "show_at_s": at, "duration_s": 8, "slot": slot, "type": kind,
            "data": {"player_a": a, "player_b": b, "bar": bar}}


def test_duel_frames_follow_the_last_duel_and_skip_noise():
    from baja_agents.overlays import duel_frames
    bars = {600: -0.42, 900: -0.2, 1200: -0.18}
    overlays = [notice(500, -0.4), notice(1150, 0.0, slot="center", kind="goal_analysis")]
    frames = duel_frames(overlays, lambda a, b, t: {"bar": bars.get(t, -0.2)}, "m001", end_s=1500)
    assert [f["show_at_s"] for f in frames] == [900]       # 600 barely moved, 1200 is under the goal
    assert frames[0]["data"] == {"player_a": "D. Mena", "player_b": "D. Verdugo", "bar": -0.2}
    assert frames[0]["source_insight"] is None and frames[0]["mode"] == "all"


def test_no_frames_before_the_first_duel_notice():
    from baja_agents.overlays import duel_frames
    assert duel_frames([notice(1000, 0.3)], lambda a, b, t: {"bar": 0.9}, "m001", end_s=1000) == []


# ------------------------------------------------------- contract v1.1
RANKING = [{"rank": 1, "player": "J. Torres", "team": "Bahía FC", "position": "ED", "mvp_score": 6.2},
           {"rank": 2, "player": "L. Montaño", "team": "Real Cardón", "position": "EI", "mvp_score": 5.9}]


def test_v11_fields_are_copied_from_the_insight(jsonschema_validator):
    from baja_agents.overlays import build
    texts = {k: {"title": "t", "text": "x"} for k in ("fan_es", "analyst_es", "fan_en", "analyst_en")}

    mvp = by_id(SAMPLE, "i05")
    mvp = {**mvp, "facts": {**mvp["facts"], "ranking": RANKING}}
    order = build(mvp, texts, mvp["t_s"] + 2, ROSTER)[0]
    assert order["data"]["ranking"] == RANKING and order["evidence"] == mvp["evidence"]
    change = mvp["facts"]["card_change"]
    assert {k: order["card"][k] for k in ("overall_from", "overall_to", "reason")} == \
        {k: change[k] for k in ("overall_from", "overall_to", "reason")}

    goal = EQUALISER  # with Torres' invisible assist
    order = build(goal, texts, goal["t_s"] + 2, ROSTER)[0]
    assert order["data"]["chain_detail"] == goal["facts"]["chain"]
    assert order["data"]["invisible_assist"]["player"] == "J. Torres"

    assert {"type", "lines_broken"} <= set(order["data"]["chain_detail"][0])

    card = DRIBBLES  # with reason_code from the engine
    order = build(card, texts, card["t_s"] + 2, ROSTER)[0]
    assert order["card"]["reason_code"] == card["facts"]["reason_code"]
    assert order["card"]["reason_params"] == card["facts"]["reason_params"]
    old = {**card, "facts": {k: v for k, v in card["facts"].items() if k not in ("reason_code", "reason_params")}}
    assert "reason_code" not in build(old, texts, card["t_s"] + 2, ROSTER)[0]["card"]

    for insight in (mvp, goal, card, old):
        for o in build(insight, texts, insight["t_s"] + 2, ROSTER):
            assert [e.message for e in jsonschema_validator.iter_errors({**o, "overlay_id": "o001"})] == []


def test_ranking_stays_out_of_the_agents_view():
    from baja_agents.narrator import slim
    mvp = by_id(SAMPLE, "i05")
    with_ranking = {**mvp, "facts": {**mvp["facts"], "ranking": RANKING}}
    assert slim(with_ranking, ROSTER) == slim(mvp, ROSTER)


# ----------------------------------------------------------- whole match
def test_offline_match_matches_the_contract(jsonschema_validator):
    from baja_insights.engine.tools import MatchQuery
    query = MatchQuery.from_files(ROOT / "data" / "m001" / "events.jsonl", ROOT / "mocks" / "teams.json")
    crew = Crew(ROSTER, "m001", Settings(cache_dir=None), offline=True, query=query)
    overlays, report = asyncio.run(crew.run_match(M001))
    frames = [o for o in overlays if o["source_insight"] is None]
    assert frames and report["duel_frames"] == len(frames)
    assert overlays
    for overlay in overlays:
        errors = [e.message for e in jsonschema_validator.iter_errors(overlay)]
        assert errors == [], (overlay["overlay_id"], errors)
    ids = [o["overlay_id"] for o in overlays]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)
    assert [o["show_at_s"] for o in overlays] == sorted(o["show_at_s"] for o in overlays)

    insights = {i["insight_id"]: i for i in M001}
    for overlay in overlays:
        if overlay["source_insight"] is None:
            continue
        insight = insights[overlay["source_insight"]]
        assert overlay["show_at_s"] >= insight["t_s"]
        if overlay["type"] == "mvp_update":
            assert overlay["data"]["mvp_score"] == insight["facts"]["mvp_score"]
        if overlay["type"] == "duel_bar":
            assert overlay["data"]["bar"] == insight["facts"]["bar"]

    types = [o["type"] for o in overlays]
    assert types.count("goal_analysis") == 4 * sum(i["type"] == "goal_chain" for i in M001)
    assert types.count("top3") == 4
    assert report["model_calls"]["calls"] == 0
