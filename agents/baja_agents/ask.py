"""Ask the match: answers fans' questions only from the engine's query functions.

``POST /api/ask`` (``contracts/chat.schema.json``). The agent calls the six functions of
``baja_insights.engine.tools.MatchQuery``, registered with the definitions in
``mocks/chat_tools_sample.json``. Code keeps the agent honest:

- every moment it asks for is clipped to the moment of the question, and only goals
  already scored can be looked up, so a live chat never reveals what comes next;
- every number in the answer must come from what the functions returned;
- a question about the future is always answered with ``no_prediction``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from baja_insights.contract import fmt_clock, parse_clock
from baja_insights.engine.tools import MatchQuery

from . import config
from .checks import EVENT_ID_KEYS, figures, numbers
from .llm import LLMRunner

log = logging.getLogger(__name__)

TOOLS_FILE = config.REPO_ROOT / "mocks" / "chat_tools_sample.json"
MATCH_END_S = 5520
MAX_FAN_FIGURES = 3  # a chat answer explains more than a graphic, which allows one
VERSION = "ask-4"

# Questions about the future. The agent still answers with what each team needs, as in the examples.
PREDICTION = re.compile(
    r"(qui[eé]n (va a ganar|ganar[aá])|va(n)? a (ganar|perder|empatar)|c[oó]mo (va a )?(terminar|acabar)[aá]?"
    r"|resultado final|pron[oó]stic|predic|probabilidad|apuesta"
    r"|who (will|is going to) win|will .{1,40} (win|lose|draw)|final score|how will it end|predict|odds|chances? (of|to) win)",
    re.IGNORECASE,
)

INSTRUCTIONS = """
You are "Ask the match", the chat of Baja-Insights, a live football broadcast. Fans ask about the match that is being
played; you answer only with data you get from your functions, at the current moment of the match.

Rules
- Always call the functions before answering. Never answer from memory, never compute or estimate numbers yourself.
- Every number you write must appear in a function result. Do not mention event ids.
- The current moment is `at`. Nothing after it exists yet: never ask about later moments and never talk about them.
- To explain a goal, call get_match_state first to get its goal_event_id, then get_goal_chain.
- `mode` fan: warm and simple, at most 3 figures besides the scoreline; say the rest in words. `mode` analyst: precise, with the key figures.
- Write in `language` (es or en). At most 3 sentences for fans and 4 for analysts.
- Refer to players by surname. Do not use gendered pronouns for players.
- `favorite_team` is the fan's team: you may speak to them about it, but the facts stay neutral.
- Use `history` for follow-ups such as "and Cota?".

Which functions to call
- Why a player is first, is doing well or rose in the MVP race: get_mvp_ranking and get_player_summary for that
  player. Explain with what the player did (stats, compared with expected_for_role, card_changes and their reason).
  The MVP score is the result, never the reason.
- How the match is going: get_match_state.
- Why a team is winning or losing, who is better, or who will win: get_match_state, and get_team_phase for EACH
  team over the same window. A number belongs only to the team whose result contains it. Explain a goal with
  get_goal_chain when it helps.
- A duel between two players: get_duel (player_a is the home player).
- A goal: get_match_state for its goal_event_id, then get_goal_chain.

Status
- answered: you answered from the functions.
- not_tracked: the fan asks for something the system does not record (it is in `not_tracked`, such as distance_km
  or top_speed_kmh). Say plainly that you don't have that data, then offer what you do have.
- not_found: the player, team or goal is not in this match (the function returns player_not_found, team_not_found
  or goal_not_found). Say so; you may name who is in the match.
- no_prediction: the fan asks who will win or how it will end. Never predict and never give probabilities.
  Say you don't make predictions, then say what each team needs, with data from the functions.
- If `prediction_question` is true, the status must be no_prediction.
- If you receive `fix`, your previous answer broke these rules: rewrite it to fix only that.
"""


class AskAnswer(BaseModel):
    status: Literal["answered", "not_tracked", "not_found", "no_prediction"]
    answer: str = Field(description="The answer, in the requested language and mode")


def load_tool_definitions(path: Path = TOOLS_FILE) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["tools"]


def event_ids(value) -> list[int]:
    """event_id values in a function result (goals, chain links, card changes, key events)."""
    found: list[int] = []
    if isinstance(value, dict):
        for k, v in value.items():
            if k in EVENT_ID_KEYS and isinstance(v, int):
                found.append(v)
            elif k in EVENT_ID_KEYS and isinstance(v, list):
                found.extend(x for x in v if isinstance(x, int))
            else:
                found.extend(event_ids(v))
    elif isinstance(value, list):
        for v in value:
            found.extend(event_ids(v))
    return found


def _without_ids(value):
    if isinstance(value, dict):
        return {k: _without_ids(v) for k, v in value.items() if k not in EVENT_ID_KEYS and k != "known_goals"}
    if isinstance(value, list):
        return [_without_ids(v) for v in value]
    return value


@dataclass
class ToolSession:
    """The functions for one question: moments clipped to ``at_s``, every call recorded."""

    query: MatchQuery
    at_s: int
    calls: list[str] = field(default_factory=list)
    results: list[dict] = field(default_factory=list)

    def _clip(self, value):
        try:
            seconds = parse_clock(value)
        except (TypeError, ValueError):
            return value  # the engine answers bad_arguments
        return fmt_clock(min(seconds, self.at_s))

    def goals_so_far(self) -> list[int]:
        return [g["event_id"] for g in self.query.get_match_state(fmt_clock(self.at_s))["goals"]]

    def call(self, name: str, arguments: dict) -> dict:
        args = {k: self._clip(v) if k in ("at", "from", "to") else v for k, v in arguments.items()}
        if name in ("get_match_state", "get_mvp_ranking", "get_player_summary", "get_duel") and "at" not in args:
            args["at"] = fmt_clock(self.at_s)
        if name == "get_team_phase":
            args.setdefault("to", fmt_clock(self.at_s))
        if name == "get_goal_chain":
            known = self.goals_so_far()
            try:
                goal_id = int(args.get("goal_event_id"))
            except (TypeError, ValueError):
                goal_id = None
            if goal_id not in known:
                result = {"error": "goal_not_found", "goal_event_id": args.get("goal_event_id"), "known_goals": known}
                self._record(name, result)
                return result
        result = self.query.dispatch(name, args)
        self._record(name, result)
        return result

    def _record(self, name: str, result: dict) -> None:
        self.calls.append(name)
        self.results.append(result)

    def allowed_numbers(self, extra: list) -> set[float]:
        base = numbers(json.dumps([_without_ids(self.results), extra], ensure_ascii=False))
        return base | {float(round(n * 100)) for n in base if 0 < n <= 1}

    def tools_used(self) -> list[str]:
        return list(dict.fromkeys(self.calls))

    def evidence(self) -> list[int]:
        return list(dict.fromkeys(i for r in self.results for i in event_ids(r) if i >= 1))[:12]

    def as_agent_tools(self, definitions: list[dict]):
        from agent_framework import tool

        def make(name: str):
            def run(**arguments) -> str:
                return json.dumps(self.call(name, arguments), ensure_ascii=False)
            run.__name__ = name
            return run

        return [tool(make(d["name"]), name=d["name"], description=d["description"], schema=d["parameters"])
                for d in definitions]


class RateLimiter:
    """At most ``per_minute`` questions that reach the model, across all viewers."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.times: list[float] = []

    def allow(self) -> bool:
        now = time.monotonic()
        self.times = [t for t in self.times if now - t < 60]
        if len(self.times) >= self.per_minute:
            return False
        self.times.append(now)
        return True


class AskTheMatch:
    name = "ask"

    def __init__(self, matches: dict[str, MatchQuery], runner: LLMRunner, client=None,
                 cache_dir: Path | None = None, timeout_s: float = 45.0, per_minute: int = 30):
        self.matches = matches
        self.runner = runner
        self.client = client
        self.cache_dir = cache_dir
        self.timeout_s = timeout_s
        self.limiter = RateLimiter(per_minute)
        self.definitions = load_tool_definitions()

    # ------------------------------------------------------------ helpers
    def _agent(self, session: ToolSession):
        from agent_framework import Agent

        return Agent(client=self.client, name=self.name, instructions=INSTRUCTIONS,
                     tools=session.as_agent_tools(self.definitions))

    def _cache_path(self, request: dict, at_s: int) -> Path | None:
        if not self.cache_dir:
            return None
        key = {k: request.get(k) for k in ("match_id", "mode", "language", "favorite_team", "history")}
        key.update(question=" ".join(request["question"].lower().split()), at_s=at_s, version=VERSION,
                   model=self.runner.model)
        digest = hashlib.sha256(json.dumps(key, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:32]
        return self.cache_dir / self.name / f"{digest}.json"

    @staticmethod
    def response(request: dict, at_s: int, status: str, answer: str | None, tools: list[str],
                 evidence: list[int] | None = None, error: str | None = None) -> dict:
        out = {"match_id": request["match_id"], "question": request["question"], "at_s": at_s,
               "status": status, "answer": answer, "tools": tools}
        if evidence:
            out["evidence"] = evidence
        if error:
            out["error"] = error
        return out

    def problems(self, session: ToolSession, request: dict, at_s: int, result: AskAnswer) -> list[str]:
        """Accuracy problems: an answer that still has one after the retry is never shown."""
        found = []
        if not session.calls:
            found.append("you answered without calling any function")
        allowed = session.allowed_numbers([request["question"], fmt_clock(at_s), at_s // 60,
                                           [h["text"] for h in request.get("history") or []]])
        invented = sorted(numbers(result.answer) - allowed)
        if invented:
            found.append(f"numbers not in any function result: {invented}")
        if not result.answer.strip():
            found.append("empty answer")
        return found

    @staticmethod
    def style_problems(request: dict, result: AskAnswer) -> list[str]:
        """Style problems: worth a retry, but an accurate answer is shown even if the retry keeps them."""
        if request["mode"] == "fan" and figures(result.answer) > MAX_FAN_FIGURES:
            return [f"a fan answer shows at most {MAX_FAN_FIGURES} figures besides the scoreline; "
                    "keep the most telling ones and say the rest in words"]
        return []

    # --------------------------------------------------------------- ask
    def would_limit(self, request: dict) -> bool:
        """True when this question would go over the per-minute limit. Cached answers never count."""
        try:
            at_s = min(parse_clock(request["at"]), MATCH_END_S)
        except (TypeError, ValueError):
            return False
        path = self._cache_path(request, at_s)
        if path and path.exists():
            return False
        return not self.limiter.allow()

    async def ask(self, request: dict) -> dict:
        at_s = min(parse_clock(request["at"]), MATCH_END_S)
        query = self.matches.get(request["match_id"])
        if query is None:
            return self.response(request, at_s, "error", None, [], error="engine_unavailable")

        path = self._cache_path(request, at_s)
        if path and path.exists():
            return json.loads(path.read_text(encoding="utf-8"))

        if self.client is None:
            return self.response(request, at_s, "error", None, [], error="agent_failed")

        prediction = bool(PREDICTION.search(request["question"]))
        home, away = query.roster.home, query.roster.away
        payload = {"question": request["question"], "at": fmt_clock(at_s), "mode": request["mode"],
                   "language": request["language"], "favorite_team": request.get("favorite_team"),
                   "history": request.get("history") or [], "home_team": home, "away_team": away,
                   "prediction_question": prediction}
        try:
            out = await asyncio.wait_for(self._answer(query, request, at_s, payload, prediction), self.timeout_s)
        except asyncio.TimeoutError:
            return self.response(request, at_s, "error", None, [], error="timeout")
        except Exception as exc:  # noqa: BLE001 - the engine failed under the agent
            log.warning("ask failed: %s", str(exc)[:200])
            return self.response(request, at_s, "error", None, [], error="engine_unavailable")

        if path and out["status"] != "error":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        return out

    async def _answer(self, query: MatchQuery, request: dict, at_s: int, payload: dict, prediction: bool) -> dict:
        session = ToolSession(query, at_s)
        result = await self.runner.run(self._agent(session), self.name, VERSION, payload, AskAnswer, cache=False)
        if result is None:
            return self.response(request, at_s, "error", None, session.tools_used(), error="agent_failed")
        problems = self.problems(session, request, at_s, result)
        style = self.style_problems(request, result)
        if problems or style:
            retry = {**payload, "previous": result.model_dump(), "fix": problems + style}
            second = await self.runner.run(self._agent(session), self.name, VERSION, retry, AskAnswer, cache=False)
            second_problems = self.problems(session, request, at_s, second) if second else ["no answer"]
            if not second_problems:
                result, problems = second, []
            elif problems:
                problems = second_problems
            # else: the first answer was accurate, only its style failed, so it stays
        if problems:
            log.warning("ask rejected: %s", problems)
            return self.response(request, at_s, "error", None, session.tools_used(), error="agent_failed")
        status = "no_prediction" if prediction else result.status
        return self.response(request, at_s, status, result.answer.strip(), session.tools_used(), session.evidence())


def load_matches(data_dir: Path, teams: Path | None = None) -> dict[str, MatchQuery]:
    """One MatchQuery per data/<folder>/events.jsonl, keyed by the match_id inside the events."""
    matches = {}
    for events in sorted(Path(data_dir).glob("*/events.jsonl")):
        query = MatchQuery.from_files(events, teams)
        matches[query.events[0]["match_id"]] = query
    return matches
