"""HTTP service for Ask the match: ``GET /healthz`` and ``POST /api/ask`` (contracts/chat.schema.json).

    python -m baja_agents serve --port 8080

CORS is open, because the UI is served from another origin (Azure Static Web Apps).
"""

from __future__ import annotations

import json
import logging

from aiohttp import web

from .ask import AskTheMatch
from .config import CONTRACTS

log = logging.getLogger(__name__)

CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Max-Age": "86400"}


def request_validator():
    from jsonschema import Draft202012Validator

    schema = json.loads((CONTRACTS / "chat.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator({"$ref": "#/$defs/request", "$defs": schema["$defs"]})


def make_app(chat: AskTheMatch) -> web.Application:
    validator = request_validator()

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

    app = web.Application(client_max_size=64 * 1024)
    app.add_routes([web.get("/healthz", healthz), web.post("/api/ask", ask), web.options("/api/ask", preflight)])
    return app


def serve(chat: AskTheMatch, host: str, port: int) -> None:
    log.warning("ask the match on http://%s:%d/api/ask, matches: %s", host, port, ", ".join(sorted(chat.matches)))
    web.run_app(make_app(chat), host=host, port=port, print=None)
