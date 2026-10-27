"""Ask the match, offline: a fake agent calls the real engine functions, so no Foundry is needed."""

import asyncio
import json
from pathlib import Path

import pytest

from baja_agents.ask import PREDICTION, AskAnswer, AskTheMatch, ToolSession, load_matches
from baja_agents.ask import load_tool_definitions as load_definitions
from baja_agents.llm import LLMRunner

ROOT = Path(__file__).resolve().parents[2]
MATCHES = load_matches(ROOT / "data", ROOT / "mocks" / "teams.json")
M001 = MATCHES["m001"]
GOALS = M001.get_match_state("90:00")["goals"]  # 0-1 at 17:40 and 1-1 at 63:09


def request(question="¿Cómo va el partido?", at="35:00", **kw):
    return {"match_id": "m001", "question": question, "at": at, "mode": "fan", "language": "es", **kw}


class FakeAskAgent:
    """Calls the given functions on the session, then answers with the next reply."""

    def __init__(self, session, script):
        self.session, self.script = session, script

    async def run(self, prompt, options=None):
        calls, answer = self.script.pop(0)
        for name, args in calls:
            self.session.call(name, args)
        return type("R", (), {"value": answer, "text": answer.model_dump_json()})()


class FakeChat(AskTheMatch):
    def __init__(self, script, **kw):
        runner = LLMRunner(max_calls=20, timeout_s=5, concurrency=2, cache_dir=None)
        super().__init__(MATCHES, runner, client=object(), **kw)
        self.script = script
        self.prompts = []

    def _agent(self, session):
        agent = FakeAskAgent(session, self.script)
        original = agent.run

        async def run(prompt, options=None):
            self.prompts.append(json.loads(prompt))
            return await original(prompt, options)
        agent.run = run
        return agent


def answer(text, status="answered"):
    return AskAnswer(status=status, answer=text)


@pytest.fixture(scope="module")
def response_validator():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((ROOT / "contracts" / "chat.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator({"$ref": "#/$defs/response", "$defs": schema["$defs"]})


# ------------------------------------------------------------- no future
def test_every_moment_is_clipped_to_the_question():
    session = ToolSession(M001, at_s=2100)
    assert session.call("get_mvp_ranking", {"at": "80:00"})["at_s"] == 2100
    assert session.call("get_match_state", {})["at_s"] == 2100
    assert session.call("get_team_phase", {"team": "Bahía FC", "from": "00:00", "to": "90:00"})["to"] == "35:00"


def test_only_goals_already_scored_can_be_looked_up():
    session = ToolSession(M001, at_s=2100)  # 35:00, after the 0-1, before the 1-1
    first, equaliser = GOALS[0]["event_id"], GOALS[1]["event_id"]
    assert "chain" in session.call("get_goal_chain", {"goal_event_id": first})
    future = session.call("get_goal_chain", {"goal_event_id": equaliser})
    assert future["error"] == "goal_not_found" and future["known_goals"] == [first]


def test_the_model_sees_team_names_not_home_and_away():
    pytest.importorskip("agent_framework")
    session = ToolSession(M001, at_s=1800)
    get_state = next(t for t in session.as_agent_tools(load_definitions()) if t.name == "get_match_state")
    seen = json.loads(get_state.func(at="30:00"))
    assert seen["possession_pct"] == {"Bahía FC": 44, "Real Cardón": 56}
    assert seen["scoreline"] == "Bahía FC 0-1 Real Cardón"
    assert session.results[-1]["possession_pct"] == {"home": 44, "away": 56}  # the checks keep the raw result


def test_flank_duels_are_the_full_backs_against_the_opposing_wingers():
    from baja_agents.ask import flank_duels
    start = flank_duels(M001, 0)
    pairs = {(d["player_a"], d["player_b"]) for d in start}
    assert pairs == {("D. Mena", "D. Verdugo"), ("P. Lugo", "L. Montaño"), ("J. Torres", "B. Haro"),
                     ("A. Olvera", "N. Ruelas")}
    assert all(d["duels"] == 0 for d in start)
    at_30 = flank_duels(M001, 1800)
    assert [d["duels"] for d in at_30] == sorted((d["duels"] for d in at_30), reverse=True)
    assert all(d["won_a"] + d["won_b"] == d["duels"] for d in at_30)
    assert at_30[0]["duels"] > 0


def test_the_agent_gets_the_flank_duels_and_may_quote_them():
    from baja_agents.ask import flank_duels
    duels = flank_duels(M001, 1800)
    top = duels[0]  # Torres vs Haro at 30:00
    text = f"Torres va ganando la banda: {top['won_a']} de {top['duels']} duelos."
    chat = FakeChat([([("get_duel", {"player_a": "Torres", "player_b": "Haro"})], answer(text))])
    out = asyncio.run(chat.ask(request("Who's winning the flank duel?", at="30:00")))
    assert chat.prompts[0]["flank_duels"] == duels and top["player_a"] == "J. Torres"
    assert out["status"] == "answered" and out["answer"] == text


def test_lineups_follow_the_substitutions():
    from baja_agents.ask import lineups
    start = lineups(M001, 0)
    bahia, cardon = start["Bahía FC"], start["Real Cardón"]
    assert len(bahia["on_pitch"]) == len(cardon["on_pitch"]) == 11
    on = {x["player"] for x in bahia["on_pitch"]} | {x["player"] for x in cardon["on_pitch"]}
    assert {"E. Quiroz", "D. Verdugo"} <= on and not {"C. Ibarra", "J. Castro", "R. Amador"} & on  # the bug's mix-up
    assert [x["player"] for x in bahia["bench"]] == ["C. Ibarra"] and bahia["on_pitch"][0]["position"] == "POR"

    later = lineups(M001, 4500)  # 75:00: Amador on for Montaño at 70:00
    cardon_on = {x["player"] for x in later["Real Cardón"]["on_pitch"]}
    assert "R. Amador" in cardon_on and "L. Montaño" not in cardon_on
    assert later["Real Cardón"]["substitutions"] == [{"clock": "70:00", "out": "L. Montaño", "in": "R. Amador"}]
    assert "L. Montaño" not in {x["player"] for x in later["Real Cardón"]["bench"]}  # subbed off is not bench

    end = lineups(M001, 5400)
    assert end["Bahía FC"]["bench"] == [] and len(end["Bahía FC"]["on_pitch"]) == 11


def test_a_lineup_question_needs_no_function_but_others_do():
    chat = FakeChat([([], answer("Bahía FC: L. Arce (POR), D. Mena (LD)..."))])
    out = asyncio.run(chat.ask(request("¿Me das las alineaciones de los equipos?", at="00:00")))
    assert out["status"] == "answered" and out["tools"] == []
    assert chat.prompts[0]["lineups"]["Bahía FC"]["on_pitch"][0]["player"] == "L. Arce"
    chat = FakeChat([([], answer("Va muy bien.")), ([], answer("Va muy bien."))])
    assert asyncio.run(chat.ask(request("¿Cómo va el partido?")))["status"] == "error"


def test_the_chat_model_gets_no_pitch_coordinates():
    pytest.importorskip("agent_framework")
    session = ToolSession(M001, at_s=4200)
    chain_tool = next(t for t in session.as_agent_tools(load_definitions()) if t.name == "get_goal_chain")
    seen = json.loads(chain_tool.func(goal_event_id=GOALS[1]["event_id"]))
    assert all("start" not in link and "end" not in link for link in seen["chain"])
    assert session.results[-1]["chain"][1]["end"] == [92, 26]  # the raw result keeps them
    assert 92.0 not in session.allowed_numbers([])


def test_duel_counts_are_not_scorelines():
    # 30:00, Bahía FC 0-1 Real Cardón. "3-1" in duels was rejected as a scoreline; only "1-0" is backwards.
    chat = FakeChat([([("get_duel", {"player_a": "Torres", "player_b": "Haro"})],
                      answer("Torres le gana a Haro 3-1 en duelos, con Real Cardón arriba 0-1."))])
    assert asyncio.run(chat.ask(request("Who's winning the flank duel?", at="30:00")))["status"] == "answered"
    from baja_agents.checks import wrong_scorelines
    assert wrong_scorelines("Real Cardón gana 1-0.", {"0-1"}) and not wrong_scorelines("ganó 3-1 los duelos", {"0-1"})


def test_not_found_needs_no_function():
    chat = FakeChat([([], answer("Messi no juega en este partido.", "not_found"))])
    out = asyncio.run(chat.ask(request("¿Cómo va jugando Messi?", at="50:00")))
    assert out["status"] == "not_found" and out["tools"] == []


def test_reasoning_effort_reaches_the_model_and_the_cache_key():
    plain = LLMRunner(max_calls=1, timeout_s=1, concurrency=1, cache_dir=None, model="m")
    low = LLMRunner(max_calls=1, timeout_s=1, concurrency=1, cache_dir=None, model="m", reasoning_effort="low")
    assert "reasoning" not in plain._options(AskAnswer)
    assert low._options(AskAnswer)["reasoning"] == {"effort": "low"}
    assert plain._key("a", "v", {}) != low._key("a", "v", {})


def test_goal_questions_get_the_goals_with_their_chains(response_validator):
    from baja_agents.ask import goals_so_far
    assert goals_so_far(M001, 600) == []
    at_35 = goals_so_far(M001, 2100)
    assert [g["scorer"] for g in at_35] == ["S. Leyva"]  # the 1-1 has not happened yet
    both = goals_so_far(M001, 4200)
    text = json.dumps(both, ensure_ascii=False)
    assert both[1]["scoreline"] == "Bahía FC 1-1 Real Cardón" and both[1]["invisible_assist"]["player"] == "J. Torres"
    assert '"event_id"' not in text and '"start"' not in text and '"end"' not in text

    chat = FakeChat([([], answer("Cota recupera, Torres arrastra a su marca, Salgado rompe dos líneas y Ramírez remata."))])
    out = asyncio.run(chat.ask(request("Why did Bahía score the equaliser?", at="70:00", language="en")))
    assert chat.prompts[0]["goals"] == both
    assert out["status"] == "answered" and out["tools"] == ["get_match_state", "get_goal_chain"]
    assert [e.message for e in response_validator.iter_errors(out)] == []

    chat = FakeChat([([("get_match_state", {})], answer("Real Cardón gana por la mínima."))])
    asyncio.run(chat.ask(request("¿Cómo va el partido?")))
    assert "goals" not in chat.prompts[0]  # only for goal questions, to keep prompts short


def test_prediction_questions_are_detected():
    for q in ("¿Quién va a ganar?", "¿Cómo va a terminar?", "Who will win?", "What are Bahía's chances to win?"):
        assert PREDICTION.search(q), q
    for q in ("¿Cómo va el partido?", "¿Quién ganó el duelo?", "Who is winning Mena vs Verdugo?"):
        assert not PREDICTION.search(q), q


# ------------------------------------------------------------- answers
def test_answer_backed_by_the_functions(response_validator):
    score = M001.get_match_state("35:00")["scoreline"]
    chat = FakeChat([([("get_match_state", {"at": "35:00"})], answer(f"Van {score['home']}-{score['away']}."))])
    out = asyncio.run(chat.ask(request()))
    assert out["status"] == "answered" and out["tools"] == ["get_match_state"]
    assert out["evidence"] == [GOALS[0]["event_id"]]
    assert [e.message for e in response_validator.iter_errors(out)] == []


def test_invented_numbers_get_one_retry_then_an_error(response_validator):
    wrong = answer("Bahía lleva 99 tiros.")
    chat = FakeChat([([("get_match_state", {})], wrong), ([], wrong)])
    out = asyncio.run(chat.ask(request()))
    assert "fix" in chat.prompts[1] and "99" in chat.prompts[1]["fix"][0]
    assert out["status"] == "error" and out["answer"] is None and out["error"] == "agent_failed"
    assert [e.message for e in response_validator.iter_errors(out)] == []


def test_the_retry_can_fix_it():
    chat = FakeChat([([("get_match_state", {})], answer("Bahía lleva 99 tiros.")),
                     ([], answer("Real Cardón gana por la mínima."))])
    assert asyncio.run(chat.ask(request()))["status"] == "answered"


def test_a_scoreline_written_backwards_is_fixed_or_rejected():
    # 60:00: Real Cardón leads 0-1 (home-away). "1-0" is how a Cardón fan would say it, and it is wrong here.
    chat = FakeChat([([("get_match_state", {})], answer("Real Cardón gana 1-0.")),
                     ([], answer("Real Cardón gana 0-1."))])
    out = asyncio.run(chat.ask(request(at="60:00")))
    assert "scoreline 1-0" in chat.prompts[1]["fix"][0]
    assert out["status"] == "answered" and out["answer"] == "Real Cardón gana 0-1."
    # The scoreline at the moment of a goal is fine too
    session = ToolSession(M001, at_s=4200)
    session.call("get_goal_chain", {"goal_event_id": GOALS[0]["event_id"]})
    assert {"0-1", "1-1"} <= session.scorelines()


def test_answering_without_functions_is_rejected():
    chat = FakeChat([([], answer("Va muy bien.")), ([], answer("Va muy bien."))])
    assert asyncio.run(chat.ask(request()))["status"] == "error"


def test_a_prediction_question_is_always_no_prediction():
    chat = FakeChat([([("get_match_state", {})], answer("No hago predicciones, pero Bahía necesita llegar más."))])
    out = asyncio.run(chat.ask(request("¿Quién va a ganar?")))
    assert out["status"] == "no_prediction" and chat.prompts[0]["prediction_question"] is True


def test_not_tracked_passes_through():
    chat = FakeChat([([("get_player_summary", {"player": "Torres"})],
                      answer("Ese dato no lo tengo: el sistema no registra la distancia.", "not_tracked"))])
    out = asyncio.run(chat.ask(request("¿Cuántos kilómetros corrió Torres?", at="70:00")))
    assert out["status"] == "not_tracked" and out["tools"] == ["get_player_summary"]


def test_too_many_figures_for_a_fan():
    stats = M001.get_player_summary("Torres", "35:00")["stats"]
    figures = ", ".join(str(v) for v in list(stats.values())[:5])
    chat = FakeChat([([("get_player_summary", {"player": "Torres"})], answer(f"Torres suma {figures}.")),
                     ([], answer("Torres está en todas."))])
    asyncio.run(chat.ask(request("¿Cómo juega Torres?")))
    assert "figures" in " ".join(chat.prompts[1]["fix"])


def test_an_accurate_answer_is_kept_when_only_its_style_fails():
    stats = M001.get_player_summary("Torres", "35:00")["stats"]
    many = f"Torres suma {', '.join(str(v) for v in list(stats.values())[:5])}."
    chat = FakeChat([([("get_player_summary", {"player": "Torres"})], answer(many)), ([], answer(many))])
    out = asyncio.run(chat.ask(request("¿Cómo juega Torres?")))
    assert out["status"] == "answered" and out["answer"] == many


def test_cached_answers_cost_nothing(tmp_path):
    chat = FakeChat([([("get_match_state", {})], answer("Real Cardón gana por la mínima."))], cache_dir=tmp_path)
    first = asyncio.run(chat.ask(request()))
    again = asyncio.run(chat.ask(request("  ¿CÓMO va el   partido? ")))  # same question, other spacing and case
    assert again == {**first, "question": first["question"]} and chat.script == []
    assert chat.would_limit(request()) is False


def test_unknown_match_and_no_client():
    chat = FakeChat([])
    assert asyncio.run(chat.ask({**request(), "match_id": "zzz"}))["error"] == "engine_unavailable"
    chat.client = None
    assert asyncio.run(chat.ask(request()))["error"] == "agent_failed"


# --------------------------------------------------------------- server
def test_server_routes():
    from aiohttp.test_utils import TestClient, TestServer
    from baja_agents.server import make_app

    async def scenario():
        chat = FakeChat([([("get_match_state", {})], answer("Real Cardón gana por la mínima."))], per_minute=1)
        async with TestClient(TestServer(make_app(chat))) as client:
            assert (await (await client.get("/healthz")).text()) == "ok"
            pre = await client.options("/api/ask")
            assert pre.status == 204 and pre.headers["Access-Control-Allow-Origin"] == "*"
            assert (await client.post("/api/ask", data="no json")).status == 400
            assert (await client.post("/api/ask", json={"question": "hola"})).status == 400
            assert (await client.post("/api/ask", json={**request(), "match_id": "zzz"})).status == 404
            ok = await client.post("/api/ask", json=request())
            assert ok.status == 200 and (await ok.json())["status"] == "answered"
            limited = await client.post("/api/ask", json=request("¿Y Torres?"))
            assert limited.status == 429

    asyncio.run(scenario())
