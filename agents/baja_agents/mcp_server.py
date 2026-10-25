"""The engine's six query functions as an MCP server (Model Context Protocol, Streamable HTTP).

    POST /mcp   JSON-RPC 2.0: initialize, tools/list, tools/call, ping

Any MCP client (Agent Framework's MCPStreamableHTTPTool, Foundry agents, Claude, VS Code...)
can ask the match the same questions as the chat, with the same guarantees:

- the tools and their descriptions come from ``mocks/chat_tools_sample.json``;
- every tool takes ``match_id`` and an optional ``as_of``, the live moment. With ``as_of``,
  every moment is clipped to it and only goals already scored can be looked up, exactly as
  in Ask the match (``ask.ToolSession``), so a live client never sees what comes next.

It is stateless, needs no SDK and answers every request with ``application/json``, which the
Streamable HTTP transport allows. It is served next to ``/api/ask`` by ``server.py``.
"""

from __future__ import annotations

import copy
import json

from baja_insights.contract import parse_clock
from baja_insights.engine.tools import MatchQuery

from . import __version__
from .ask import MATCH_END_S, ToolSession, load_tool_definitions

# Newest first. A client asking for one of these gets it back; any other gets the newest.
PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26")
SERVER_INFO = {"name": "baja-insights", "title": "Baja-Insights match engine", "version": __version__}
INSTRUCTIONS = (
    "Query functions of a synthetic football match, computed by a deterministic engine. Numbers are exact. "
    "Call list_matches first. Pass as_of (MM:SS) to ask as if the match were live at that moment: nothing after "
    "it is returned. Data the engine does not record appears in not_tracked; never fill it in."
)

PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS = -32700, -32600, -32601, -32602
EMPTY_LISTS = {"prompts/list": "prompts", "resources/list": "resources", "resources/templates/list": "resourceTemplates"}


class MatchTools:
    """MCP tool definitions and calls over a set of matches."""

    def __init__(self, matches: dict[str, MatchQuery]):
        self.matches = matches
        self.tools = [self._with_match_args(d) for d in load_tool_definitions()] + [{
            "name": "list_matches",
            "description": "Matches this server can answer about, with their teams and final scoreline.",
            "inputSchema": {"type": "object", "properties": {}},
        }]
        self.names = {t["name"] for t in self.tools}

    def _with_match_args(self, definition: dict) -> dict:
        schema = copy.deepcopy(definition["parameters"])
        props = schema.setdefault("properties", {})
        props["match_id"] = {"type": "string", "description": "Match id from list_matches, for example m001.",
                             "default": "m001"}
        props["as_of"] = {"type": "string", "description": "Optional live moment MM:SS. Nothing after it is returned."}
        return {"name": definition["name"], "description": definition["description"], "inputSchema": schema}

    def list_matches(self) -> dict:
        out = []
        for match_id, query in sorted(self.matches.items()):
            final = query.get_match_state("90:00")
            out.append({"match_id": match_id, "home": query.roster.home, "away": query.roster.away,
                        "final_scoreline": final["scoreline"]})
        return {"matches": out}

    def call(self, name: str, arguments: dict) -> dict:
        """Result of one tool, as the engine returns it. Engine errors come back as data, like in the chat."""
        if name == "list_matches":
            return self.list_matches()
        args = dict(arguments or {})
        match_id = args.pop("match_id", "m001")
        query = self.matches.get(match_id)
        if query is None:
            return {"error": "match_not_found", "match_id": match_id, "known_matches": sorted(self.matches)}
        as_of = args.pop("as_of", None)
        try:
            at_s = MATCH_END_S if as_of in (None, "") else min(parse_clock(as_of), MATCH_END_S)
        except (TypeError, ValueError):
            return {"error": "bad_arguments", "tool": name, "detail": f"as_of is not a match time: {as_of!r}"}
        if as_of in (None, ""):
            return query.dispatch(name, args)
        return ToolSession(query, at_s).call(name, args)


def _error(request_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _result(request_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def handle(tools: MatchTools, message) -> dict | None:
    """One JSON-RPC message in, its response out (None for notifications, which get no answer)."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        return _error(message.get("id") if isinstance(message, dict) else None, INVALID_REQUEST, "invalid request")
    method, request_id, params = message["method"], message.get("id"), message.get("params") or {}
    if "id" not in message:  # notification: notifications/initialized, notifications/cancelled...
        return None

    if method == "initialize":
        asked = params.get("protocolVersion")
        version = asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
        return _result(request_id, {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
                                    "serverInfo": SERVER_INFO, "instructions": INSTRUCTIONS})
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(request_id, {"tools": tools.tools})
    if method in EMPTY_LISTS:  # only tools are offered, but some clients ask for these anyway
        return _result(request_id, {EMPTY_LISTS[method]: []})
    if method == "tools/call":
        name, arguments = params.get("name"), params.get("arguments") or {}
        if name not in tools.names:
            return _error(request_id, INVALID_PARAMS, f"unknown tool: {name}")
        if not isinstance(arguments, dict):
            return _error(request_id, INVALID_PARAMS, "arguments must be an object")
        result = tools.call(name, arguments)
        return _result(request_id, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                                    "structuredContent": result, "isError": "error" in result})
    return _error(request_id, METHOD_NOT_FOUND, f"method not found: {method}")


def handle_body(tools: MatchTools, body: bytes) -> tuple[int, dict | list | None]:
    """HTTP status and JSON body for one POST /mcp. 202 with no body when only notifications came in."""
    try:
        message = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 400, _error(None, PARSE_ERROR, "parse error")
    if isinstance(message, list):  # batches, from protocol 2025-03-26
        replies = [r for r in (handle(tools, m) for m in message) if r is not None]
        return (200, replies) if replies else (202, None)
    reply = handle(tools, message)
    return (200, reply) if reply is not None else (202, None)
