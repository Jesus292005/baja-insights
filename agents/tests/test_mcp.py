"""The engine functions as an MCP server: the protocol, offline, and a real MCP client when one is installed."""

import asyncio
import json
import os
from pathlib import Path

import pytest

from baja_agents import mcp_server
from baja_agents.ask import AskTheMatch, load_matches
from baja_agents.llm import LLMRunner
from baja_agents.server import make_app

ROOT = Path(__file__).resolve().parents[2]
MATCHES = load_matches(ROOT / "data", ROOT / "mocks" / "teams.json")
TOOLS = mcp_server.MatchTools(MATCHES)
GOALS = [g["event_id"] for g in MATCHES["m001"].get_match_state("90:00")["goals"]]
LEADER_AT_35 = MATCHES["m001"].get_mvp_ranking("35:00", 1)["ranking"][0]["player"]  # whoever the engine has first


def rpc(method, params=None, id_=1):
    message = {"jsonrpc": "2.0", "method": method}
    if id_ is not None:
        message["id"] = id_
    if params is not None:
        message["params"] = params
    return message


def call(message):
    status, body = mcp_server.handle_body(TOOLS, json.dumps(message).encode())
    return status, body


def tool_result(name, **arguments):
    status, body = call(rpc("tools/call", {"name": name, "arguments": arguments}))
    assert status == 200
    return body["result"]


# ------------------------------------------------------------- protocol
def test_initialize_negotiates_the_protocol_version():
    _, body = call(rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t"}}))
    result = body["result"]
    assert result["protocolVersion"] == "2025-06-18" and "tools" in result["capabilities"]
    _, body = call(rpc("initialize", {"protocolVersion": "1999-01-01"}))
    assert body["result"]["protocolVersion"] == mcp_server.PROTOCOL_VERSIONS[0]


def test_notifications_get_202_and_no_body():
    assert call(rpc("notifications/initialized", id_=None)) == (202, None)


def test_tools_are_the_contract_functions_plus_list_matches():
    _, body = call(rpc("tools/list"))
    tools = {t["name"]: t for t in body["result"]["tools"]}
    contract = json.loads((ROOT / "mocks" / "chat_tools_sample.json").read_text(encoding="utf-8"))["tools"]
    assert set(tools) == {d["name"] for d in contract} | {"list_matches"}
    for d in contract:
        assert tools[d["name"]]["description"] == d["description"]
        assert {"match_id", "as_of"} <= set(tools[d["name"]]["inputSchema"]["properties"])


def test_tool_call_returns_the_engine_result_as_text_and_structured():
    result = tool_result("get_mvp_ranking", at="35:00", top=3)
    assert result["isError"] is False
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]
    assert result["structuredContent"]["ranking"][0]["player"] == LEADER_AT_35


def test_as_of_never_returns_the_future():
    assert tool_result("get_mvp_ranking", at="80:00", as_of="35:00")["structuredContent"]["at"] == "35:00"
    future = tool_result("get_goal_chain", goal_event_id=GOALS[1], as_of="35:00")
    assert future["structuredContent"]["error"] == "goal_not_found"
    assert future["structuredContent"]["known_goals"] == [GOALS[0]]
    assert future["isError"] is False  # an answer ("not scored yet"), not a failure
    # without as_of the whole match is there, for post-match analysis
    assert "chain" in tool_result("get_goal_chain", goal_event_id=GOALS[1])["structuredContent"]


def test_list_matches_and_unknown_match():
    matches = tool_result("list_matches")["structuredContent"]["matches"]
    assert {m["match_id"] for m in matches} == set(MATCHES)
    assert tool_result("get_match_state", at="10:00", match_id="zzz")["structuredContent"]["error"] == "match_not_found"
    bad = tool_result("get_match_state", at="10:00", as_of="99:99")
    assert bad["structuredContent"]["error"] == "bad_arguments" and bad["isError"] is True
    assert tool_result("get_match_state", at="10:00", match_id="zzz")["isError"] is False


def test_protocol_errors():
    assert call(rpc("tools/call", {"name": "nope", "arguments": {}}))[1]["error"]["code"] == mcp_server.INVALID_PARAMS
    assert call(rpc("sampling/createMessage"))[1]["error"]["code"] == mcp_server.METHOD_NOT_FOUND
    assert call({"id": 1, "method": "ping"})[1]["error"]["code"] == mcp_server.INVALID_REQUEST
    assert mcp_server.handle_body(TOOLS, b"{not json")[0] == 400
    assert call(rpc("prompts/list"))[1]["result"] == {"prompts": []}


def test_batches():
    status, body = call([rpc("ping", id_=1), rpc("notifications/initialized", id_=None), rpc("tools/list", id_=2)])
    assert status == 200 and [r["id"] for r in body] == [1, 2]


# --------------------------------------------------------------- server
def chat():
    return AskTheMatch(MATCHES, LLMRunner(max_calls=0, timeout_s=1, concurrency=1, cache_dir=None))


def test_mcp_route_next_to_the_chat():
    from aiohttp.test_utils import TestClient, TestServer

    async def scenario():
        async with TestClient(TestServer(make_app(chat()))) as client:
            ok = await client.post("/mcp", json=rpc("tools/list"))
            assert ok.status == 200 and ok.headers["Access-Control-Allow-Origin"] == "*"
            assert (await client.post("/mcp", json=rpc("notifications/initialized", id_=None))).status == 202
            assert (await client.get("/mcp")).status == 405
            assert (await client.options("/mcp")).status == 204

    asyncio.run(scenario())


# ---------------------------------------------------------- real client
def as_json(result):
    """A tool result from Agent Framework's MCP client (a string or a list of Content) as JSON."""
    if isinstance(result, str):
        return json.loads(result)
    texts = [c.text for c in result if getattr(c, "text", None)]
    assert texts, result
    return json.loads(texts[0])


def test_reading_a_client_result():
    pytest.importorskip("agent_framework")
    from agent_framework import Content

    assert as_json([Content.from_text('{"a": 1}')]) == {"a": 1}
    assert as_json('{"a": 1}') == {"a": 1}


def test_a_real_mcp_client_can_use_it():
    """Agent Framework's MCP client, on the official MCP SDK. Required in CI (REQUIRE_MCP_CLIENT=1)."""
    if os.environ.get("REQUIRE_MCP_CLIENT"):
        import mcp  # noqa: F401  - fail loudly in CI instead of skipping
    else:
        pytest.importorskip("mcp")
    from agent_framework import MCPStreamableHTTPTool
    from aiohttp.test_utils import TestServer

    async def scenario():
        server = TestServer(make_app(chat()))
        await server.start_server()
        try:
            async with MCPStreamableHTTPTool(name="baja", url=str(server.make_url("/mcp")), load_prompts=False) as tool:
                names = {f.name for f in tool.functions}
                assert {"get_match_state", "get_mvp_ranking", "get_goal_chain", "list_matches"} <= names
                ranking = as_json(await tool.call_tool("get_mvp_ranking", at="35:00", top=3, match_id="m001"))
                assert ranking["at"] == "35:00" and ranking["ranking"][0]["player"] == LEADER_AT_35
                future = as_json(await tool.call_tool("get_goal_chain", goal_event_id=GOALS[1], as_of="35:00"))
                assert future["error"] == "goal_not_found" and future["known_goals"] == [GOALS[0]]
                # a malformed call is the only tool error, which Agent Framework raises
                with pytest.raises(Exception, match="bad_arguments"):
                    await tool.call_tool("get_match_state", at="10:00", as_of="99:99")
        finally:
            await server.close()

    asyncio.run(scenario())
