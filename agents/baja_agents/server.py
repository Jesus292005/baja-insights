"""HTTP service for Ask the match: ``GET /healthz``, ``POST /api/ask`` (contracts/chat.schema.json),
``POST /api/chat-overlay`` (an answer as a ``chat_answer`` graphics order, for the producer) and
``POST /mcp``, the engine's query functions as an MCP server (``mcp_server.py``).

    python -m baja_agents serve --port 8080

CORS is open, because the UI is served from another origin (Azure Static Web Apps).
"""

from __future__ import annotations

import json
import logging

from aiohttp import web

from . import mcp_server
from .ask import MATCH_END_S, AskTheMatch
from .config import CONTRACTS
from .overlays import chat_answer_order

log = logging.getLogger(__name__)

CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, GET, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Accept, Mcp-Session-Id, MCP-Protocol-Version, Last-Event-ID",
        "Access-Control-Max-Age": "86400"}


SLOTS = ("top_right", "lower_third", "side_panel", "bottom_bar", "center", "full_screen")


def request_validator(definition: str = "request"):
    from jsonschema import Draft202012Validator

    schema = json.loads((CONTRACTS / "chat.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator({"$ref": f"#/$defs/{definition}", "$defs": schema["$defs"]})


def chat_overlay_problems(body, answers) -> list[str]:
    """What is wrong with a POST /api/chat-overlay body: {answer, mode, language, show_at_s?, slot?}."""
    if not isinstance(body, dict):
        return ["the body must be an object"]
    problems = [f"answer: {e.message}" for e in answers.iter_errors(body.get("answer"))]
    if body.get("mode") not in ("fan", "analyst"):
        problems.append("mode must be fan or analyst")
    if body.get("language") not in ("es", "en"):
        problems.append("language must be es or en")
    show = body.get("show_at_s")
    if show is not None and (not isinstance(show, int) or isinstance(show, bool) or not 0 <= show <= MATCH_END_S):
        problems.append(f"show_at_s must be a whole number of match seconds, 0 to {MATCH_END_S}")
    if body.get("slot") is not None and body["slot"] not in SLOTS:
        problems.append(f"slot must be one of {', '.join(SLOTS)}")
    return problems


def make_app(chat: AskTheMatch) -> web.Application:
    validator = request_validator()
    answers = request_validator("response")
    tools = mcp_server.MatchTools(chat.matches)

    def reply(body: dict, status: int = 200) -> web.Response:
        return web.json_response(body, status=status, headers=CORS, dumps=lambda o: json.dumps(o, ensure_ascii=False))

    async def healthz(_: web.Request) -> web.Response:
        return web.Response(text="ok", headers=CORS)

    async def preflight(_: web.Request) -> web.Response:
        return web.Response(status=204, headers=CORS)

    async def ask(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return reply({"error": "bad_request", "detail": "the body is not JSON"}, 400)
        errors = [e.message for e in validator.iter_errors(body)]
        if errors:
            return reply({"error": "bad_request", "detail": errors[:5]}, 400)
        if body["match_id"] not in chat.matches:
            return reply({"error": "match_not_found", "known_matches": sorted(chat.matches)}, 404)
        if chat.would_limit(body):
            return reply({"error": "rate_limited", "detail": "too many questions this minute, try again shortly"}, 429)
        return reply(await chat.ask(body))

    async def chat_overlay(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return reply({"error": "bad_request", "detail": "the body is not JSON"}, 400)
        problems = chat_overlay_problems(body, answers)
        if problems:
            return reply({"error": "bad_request", "detail": problems[:5]}, 400)
        try:
            order = chat_answer_order(body["answer"], body["mode"], body["language"], body.get("show_at_s"),
                                      body.get("slot") or "side_panel")
        except ValueError as exc:
            return reply({"error": "no_answer", "detail": str(exc)}, 422)
        return reply(order)

    async def mcp(request: web.Request) -> web.Response:
        status, body = mcp_server.handle_body(tools, await request.read())
        if body is None:
            return web.Response(status=status, headers=CORS)
        return reply(body, status)

    async def mcp_no_stream(_: web.Request) -> web.Response:
        # Stateless server: no server-initiated stream (GET) and no session to close (DELETE).
        return web.Response(status=405, headers={**CORS, "Allow": "POST, OPTIONS"})

    app = web.Application(client_max_size=64 * 1024)
    app.add_routes([web.get("/healthz", healthz), web.post("/api/ask", ask), web.options("/api/ask", preflight),
                    web.post("/api/chat-overlay", chat_overlay), web.options("/api/chat-overlay", preflight),
                    web.post("/mcp", mcp), web.get("/mcp", mcp_no_stream), web.delete("/mcp", mcp_no_stream),
                    web.options("/mcp", preflight)])
    return app


def serve(chat: AskTheMatch, host: str, port: int) -> None:
    log.warning("ask the match on http://%s:%d/api/ask, matches: %s", host, port, ", ".join(sorted(chat.matches)))
    web.run_app(make_app(chat), host=host, port=port, print=None)
