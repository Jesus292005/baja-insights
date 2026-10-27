"""chat_answer orders: a chat answer put on screen by the producer (overlay.schema.json, contract v1.1)."""

import asyncio
import json
from pathlib import Path

import pytest

from baja_agents.overlays import CHAT_MAX_S, CHAT_MIN_S, chat_answer_order

ROOT = Path(__file__).resolve().parents[2]

ANSWER = {"match_id": "m001", "question": "¿Quién lidera la carrera al MVP?", "at_s": 2100, "status": "answered",
          "answer": "Leyva va primero porque ha recuperado 7 balones en campo rival.",
          "tools": ["get_player_summary", "get_mvp_ranking"], "evidence": [400, 254]}


@pytest.fixture(scope="module")
def overlay_validator():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((ROOT / "contracts" / "overlay.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


def errors(validator, order):
    return [e.message for e in validator.iter_errors(order)]


def test_the_order_matches_the_contract_for_every_status(overlay_validator):
    for status in ("answered", "not_tracked", "not_found", "no_prediction"):
        order = chat_answer_order({**ANSWER, "status": status}, "fan", "es")
        assert errors(overlay_validator, order) == [], status
        assert order["type"] == "chat_answer" and order["source_insight"] is None


def test_everything_comes_from_the_answer():
    order = chat_answer_order(ANSWER, "analyst", "en")
    assert order["title"] == ANSWER["question"] and order["text"] == ANSWER["answer"]
    assert order["data"] == {k: ANSWER[k] for k in ("question", "status", "tools", "evidence")}
    assert order["show_at_s"] == 2100 and order["show_at"] == "35:00" and order["period"] == 1
    assert (order["mode"], order["language"], order["slot"]) == ("analyst", "en", "side_panel")


def test_the_id_is_stable_so_the_same_answer_is_not_shown_twice():
    assert chat_answer_order(ANSWER, "fan", "es")["overlay_id"] == chat_answer_order(ANSWER, "fan", "es")["overlay_id"]
    assert chat_answer_order(ANSWER, "fan", "es")["overlay_id"] != chat_answer_order(ANSWER, "fan", "en")["overlay_id"]


def test_timing_title_and_slot(overlay_validator):
    short = chat_answer_order({**ANSWER, "answer": "Sí."}, "fan", "es")
    long = chat_answer_order({**ANSWER, "answer": "palabra " * 200, "question": "¿" + "x" * 120 + "?"}, "fan", "es")
    assert short["duration_s"] == CHAT_MIN_S and long["duration_s"] == CHAT_MAX_S
    assert len(long["title"]) == 80 and long["title"].endswith("…")
    later = chat_answer_order(ANSWER, "fan", "es", show_at_s=3000, slot="lower_third")
    assert (later["show_at_s"], later["period"], later["slot"]) == (3000, 2, "lower_third")
    assert chat_answer_order({**ANSWER, "at_s": 5520}, "fan", "es", show_at_s=6000)["show_at_s"] == 5520
    for order in (short, long, later):
        assert errors(overlay_validator, order) == []


def test_an_error_answer_cannot_go_on_screen():
    failed = {**ANSWER, "status": "error", "answer": None, "error": "agent_failed"}
    with pytest.raises(ValueError):
        chat_answer_order(failed, "fan", "es")


def test_the_endpoint(overlay_validator):
    from aiohttp.test_utils import TestClient, TestServer
    from baja_agents.ask import AskTheMatch, load_matches
    from baja_agents.llm import LLMRunner
    from baja_agents.server import make_app

    chat = AskTheMatch(load_matches(ROOT / "data", ROOT / "mocks" / "teams.json"),
                       LLMRunner(max_calls=0, timeout_s=1, concurrency=1, cache_dir=None))

    async def scenario():
        async with TestClient(TestServer(make_app(chat))) as client:
            ok = await client.post("/api/chat-overlay", json={"answer": ANSWER, "mode": "fan", "language": "es"})
            assert ok.status == 200 and ok.headers["Access-Control-Allow-Origin"] == "*"
            assert errors(overlay_validator, await ok.json()) == []
            assert (await client.options("/api/chat-overlay")).status == 204
            bad = await client.post("/api/chat-overlay", json={"answer": ANSWER, "mode": "all", "language": "fr"})
            assert bad.status == 400 and len((await bad.json())["detail"]) == 2
            assert (await client.post("/api/chat-overlay", json={"answer": {"question": "x"}, "mode": "fan",
                                                                 "language": "es"})).status == 400
            assert (await client.post("/api/chat-overlay", json={"answer": ANSWER, "mode": "fan", "language": "es",
                                                                 "show_at_s": 9999})).status == 400
            failed = {**ANSWER, "status": "error", "answer": None, "error": "agent_failed"}
            no_text = await client.post("/api/chat-overlay", json={"answer": failed, "mode": "fan", "language": "es"})
            assert no_text.status == 422

    asyncio.run(scenario())
