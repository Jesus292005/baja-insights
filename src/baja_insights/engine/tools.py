"""Query functions for the "Ask the match" agent (contract v1, see mocks/chat_tools_sample.json).

Every function answers from the engine state at a given match time, never from
memory. If a datum does not exist the result says so (``error`` or ``not_tracked``),
so the agent can answer "I don't know" instead of inventing.

Member 2 can expose ``MatchQuery.dispatch`` as Foundry function tools or as an
MCP server without touching the engine.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..contract import event_t_s, fmt_clock, parse_clock, period_of
from ..roster import Roster, overall
from .core import InsightEngine
from .state import NOT_TRACKED

TOOL_NAMES = ("get_match_state", "get_mvp_ranking", "get_player_summary", "get_duel",
              "get_team_phase", "get_goal_chain")


class MatchQuery:
    def __init__(self, events: list[dict], roster: Roster):
        self.roster = roster
        self.events = sorted(events, key=lambda e: (event_t_s(e), e["event_id"]))
        self._times = [event_t_s(e) for e in self.events]

    @classmethod
    def from_files(cls, events_path: str | Path, teams_path: str | Path | None = None) -> "MatchQuery":
        text = Path(events_path).read_text(encoding="utf-8")
        events = json.loads(text) if text.lstrip().startswith("[") else [json.loads(l) for l in text.splitlines() if l.strip()]
        return cls(events, Roster.load(teams_path))

    # ----------------------------------------------------------- plumbing
    def engine_at(self, at_s: int) -> InsightEngine:
        return self._engine_upto(sum(1 for t in self._times if t <= at_s))

    @lru_cache(maxsize=64)
    def _engine_upto(self, n_events: int) -> InsightEngine:
        engine = InsightEngine(self.roster)
        for event in self.events[:n_events]:
            engine.process(event)
        if n_events and engine.state.t < self._times[n_events - 1]:
            engine.state.t = self._times[n_events - 1]
        return engine

    def _at(self, at) -> tuple[int, InsightEngine]:
        at_s = parse_clock(at)
        engine = self.engine_at(at_s)
        engine.state.t = max(engine.state.t, min(at_s, 5400))
        return at_s, engine

    def dispatch(self, name: str, arguments: dict) -> dict:
        if name not in TOOL_NAMES:
            return {"error": "unknown_tool", "tool": name}
        try:
            return getattr(self, name)(**arguments)
        except (KeyError, ValueError, TypeError) as exc:
            return {"error": "bad_arguments", "tool": name, "detail": str(exc)}

    # ----------------------------------------------------------- tools
    def get_match_state(self, at) -> dict:
        at_s, engine = self._at(at)
        st = engine.state
        stats = {team: st.window_stats(team, 0, at_s + 1) for team in (st.home, st.away)}
        goals = [{"event_id": gid, "t_s": st.by_id[gid]["t_s"], "team": st.by_id[gid]["team"],
                  "scorer": st.by_id[gid]["player"], "assist": st.by_id[gid].get("assist")} for gid in st.goals]
        return {"at": fmt_clock(at_s), "at_s": at_s, "period": period_of(at_s), "scoreline": dict(st.scoreline),
                "goals": goals, "xg": {st.side(t): stats[t]["xg"] for t in stats},
                "possession_pct": {st.side(t): stats[t]["possession_pct"] for t in stats}}

    def get_mvp_ranking(self, at, top: int = 5) -> dict:
        at_s, engine = self._at(at)
        st = engine.state
        return {"at": fmt_clock(at_s), "at_s": at_s, "ranking": st.ranking_rows(top)}

    def get_player_summary(self, player: str, at) -> dict:
        found = self.roster.find(player)
        if found is None:
            return {"error": "player_not_found", "player": player, "known_players": sorted(self.roster.players)}
        at_s, engine = self._at(at)
        st = engine.state
        ps = st.players[found.name]
        card = dict(ps.card)
        card["overall"] = overall(ps.card)
        key_events = [e for _, e in sorted(ps.point_events, key=lambda pe: (-pe[0], pe[1]))[:3]]
        return {
            "player": ps.name, "team": ps.team, "position": ps.position, "at": fmt_clock(at_s), "at_s": at_s,
            "minutes_played": round(ps.minutes(at_s), 1), "mvp_rank": st.rank_of(ps.name), "mvp_score": st.mvp(ps),
            "vs_role": st.vs_role(ps), "stats": dict(ps.stats), "expected_for_role": st.expected(ps),
            "card": card,
            "card_changes": [{k: c[k] for k in ("attribute", "from", "to", "delta", "reason", "overall_from",
                                                "overall_to", "event_id", "t_s")} for c in ps.card_changes],
            "key_events": key_events, "not_tracked": list(NOT_TRACKED),
        }

    def get_duel(self, player_a: str, player_b: str, at) -> dict:
        a, b = self.roster.find(player_a), self.roster.find(player_b)
        if a is None or b is None:
            return {"error": "player_not_found", "player": player_a if a is None else player_b}
        if a.team == b.team:
            return {"error": "same_team", "players": [a.name, b.name]}
        _, engine = self._at(at)
        facts = engine.duel_facts(a.name, b.name)
        facts["flipped"] = False
        return facts

    def get_team_phase(self, team: str, **window) -> dict:
        name = self.roster.find_team(team)
        if name is None:
            return {"error": "team_not_found", "team": team, "known_teams": [self.roster.home, self.roster.away]}
        start = parse_clock(window.get("from", "00:00"))
        end = parse_clock(window.get("to", "90:00"))
        if end <= start:
            return {"error": "empty_window", "from": fmt_clock(start), "to": fmt_clock(end)}
        _, engine = self._at(end)
        stats = engine.state.window_stats(name, start, end)
        return {"team": name, "from": fmt_clock(start), "to": fmt_clock(end), **stats}

    def get_goal_chain(self, goal_event_id: int) -> dict:
        engine = self.engine_at(10**9)
        facts = engine.goal_chains.get(int(goal_event_id))
        if facts is None:
            return {"error": "goal_not_found", "goal_event_id": goal_event_id,
                    "known_goals": sorted(engine.goal_chains)}
        return facts
