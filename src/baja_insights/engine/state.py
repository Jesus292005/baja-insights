"""Accumulated match state. Updated event by event, read by detectors and chat tools."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from ..contract import (
    DEF_ACTION_EVENTS, event_t_s, in_opponent_half, period_of, progress_from_own_goal,
)
from ..roster import Roster, overall
from . import params as P
from .scoring import expected_for_role, is_progressive, mvp_score, pass_difficulty, vs_role

STAT_KEYS = (
    "passes", "passes_completed", "progressive_passes", "line_breaking_passes", "key_passes",
    "assists", "shots", "shots_on_target", "xg", "goals", "recoveries", "recoveries_opp_half",
    "tackles", "tackles_won", "duels_total", "duels_won", "pressures", "fouls_committed",
    "fouls_received", "off_ball_runs",
)
OWNER_EVENTS = ("pass", "shot", "recovery", "off_ball_run", "goal")
NOT_TRACKED = ("distance_km", "sprints", "top_speed_kmh", "heatmap", "touches_off_ball")


@dataclass
class PlayerState:
    name: str
    team: str
    position: str
    card: dict
    on_since: int | None = None
    minutes_acc: float = 0.0
    raw_points: float = 0.0
    stats: dict = field(default_factory=lambda: {k: (0.0 if k == "xg" else 0) for k in STAT_KEYS})
    card_gains: dict = field(default_factory=lambda: defaultdict(int))
    card_last_t: dict = field(default_factory=dict)
    card_changes: list = field(default_factory=list)
    point_events: list = field(default_factory=list)          # (points, event_id)
    opp_half_recovery_times: deque = field(default_factory=deque)
    duel_streak: int = 0

    def minutes(self, at: int) -> float:
        live = (at - self.on_since) / 60.0 if self.on_since is not None else 0.0
        return round(self.minutes_acc + max(live, 0.0), 2)

    def add_points(self, points: float, event_id: int | None) -> None:
        self.raw_points += points
        if event_id is not None and points:
            self.point_events.append((round(points, 3), event_id))


@dataclass
class Possession:
    pid: int
    start_t: int
    owner: str | None = None
    end_t: int | None = None
    events: list = field(default_factory=list)
    last_complete_pass: dict | None = None
    off_ball_runs: list = field(default_factory=list)
    live: list = field(default_factory=list)          # (start_t, end_t) of ball-in-play time


class MatchState:
    def __init__(self, roster: Roster, match_id: str | None = None):
        self.roster = roster
        self.home = roster.home
        self.away = roster.away
        self.match_id = match_id or roster.match.get("match_id", "m001")
        self.t = 0
        self.period = 1
        self.scoreline = {"home": 0, "away": 0}
        self.events: list[dict] = []
        self.by_id: dict[int, dict] = {}
        self.players: dict[str, PlayerState] = {}
        self.possessions: dict[int, Possession] = {}
        self.current_pid: int | None = None
        self._last_t: int | None = None
        self.goals: list[int] = []
        self.finished = False
        self.recent_pressures: deque = deque()
        # Team time series used by windows: (t, value...)
        self.team_passes = defaultdict(list)        # team -> [(t, completed)]
        self.team_shots = defaultdict(list)         # team -> [(t, xg, on_target)]
        self.team_recoveries = defaultdict(list)    # team -> [(t, opp_half, event_id)]
        self.team_def_actions = defaultdict(list)   # team -> [(t, height_m)]
        self.duel_pairs = defaultdict(list)         # (home_player, away_player) -> [(t, winner, event_id)]
        for p in roster.players.values():
            self.players[p.name] = PlayerState(
                name=p.name, team=p.team, position=p.position, card=dict(p.card),
                on_since=0 if p.starter else None,
            )

    # ------------------------------------------------------------------ helpers
    def player(self, name: str | None, event: dict | None = None) -> PlayerState | None:
        if not name:
            return None
        if name not in self.players and event is not None:
            # Unknown player in the stream: keep going instead of crashing the broadcast.
            self.players[name] = PlayerState(name=name, team=event.get("team") or "?",
                                             position=event.get("position") or "MC",
                                             card={}, on_since=self.t)
        return self.players.get(name)

    def baseline(self, position: str) -> dict:
        return self.roster.baselines.get(position, self.roster.baselines["MC"])

    def role_actual(self, ps: PlayerState) -> dict:
        return {k: ps.stats[k] for k in P.ROLE_STATS}

    def vs_role(self, ps: PlayerState, at: int | None = None) -> float:
        return vs_role(self.role_actual(ps), self.baseline(ps.position), ps.minutes(self.t if at is None else at))

    def expected(self, ps: PlayerState) -> dict:
        return {k: round(v, 2) for k, v in expected_for_role(self.baseline(ps.position), ps.minutes(self.t)).items()}

    def mvp(self, ps: PlayerState) -> float:
        minutes = ps.minutes(self.t)
        return mvp_score(ps.raw_points, self.vs_role(ps), minutes)

    def ranking(self) -> list[tuple[str, float]]:
        rows = [(name, self.mvp(ps)) for name, ps in self.players.items()
                if ps.minutes(self.t) > 0 and ps.position != "POR"]
        rows.sort(key=lambda r: (-r[1], -self.players[r[0]].raw_points, r[0]))
        return rows

    def rank_of(self, name: str, ranking: list[tuple[str, float]] | None = None) -> int | None:
        for i, (n, _) in enumerate(ranking or self.ranking(), start=1):
            if n == name:
                return i
        return None

    def side(self, team: str) -> str:
        return "home" if team == self.home else "away"

    # ---------------------------------------------------------------- cards
    def card_change(self, name: str, attribute: str, delta: int, reason: str, event_id: int) -> dict | None:
        ps = self.players.get(name)
        if ps is None or attribute not in ps.card:
            return None
        last = ps.card_last_t.get(attribute)
        if last is not None and self.t - last < P.CARD_ATTRIBUTE_COOLDOWN_S:
            return None
        room = min(P.CARD_MAX_GAIN_PER_ATTRIBUTE - ps.card_gains[attribute], P.CARD_MAX_VALUE - ps.card[attribute])
        delta = min(delta, room)
        if delta <= 0:
            return None
        overall_from = overall(ps.card)
        before = ps.card[attribute]
        ps.card[attribute] = before + delta
        ps.card_gains[attribute] += delta
        ps.card_last_t[attribute] = self.t
        change = {
            "attribute": attribute, "from": before, "to": before + delta, "delta": delta,
            "reason": reason, "overall_from": overall_from, "overall_to": overall(ps.card),
            "event_id": event_id, "t_s": self.t,
        }
        ps.card_changes.append(change)
        return change

    # ------------------------------------------------------------- windows
    def possession_pct(self, team: str, start: int, end: int) -> float | None:
        owned = defaultdict(float)
        for pos in self.possessions.values():
            if pos.owner is None:
                continue
            for seg_start, seg_end in pos.live:
                overlap = min(seg_end, end) - max(seg_start, start)
                if overlap > 0:
                    owned[pos.owner] += overlap
        total = sum(owned.values())
        return round(100 * owned[team] / total) if total else None

    def window_stats(self, team: str, start: int, end: int) -> dict:
        passes = [c for t, c in self.team_passes[team] if start <= t < end]
        shots = [(xg, on) for t, xg, on in self.team_shots[team] if start <= t < end]
        recs = [opp for t, opp, _ in self.team_recoveries[team] if start <= t < end]
        heights = [h for t, h in self.team_def_actions[team] if start <= t < end]
        minutes = max((end - start) / 60.0, 1e-9)
        return {
            "possession_pct": self.possession_pct(team, start, end),
            "pass_accuracy_pct": round(100 * sum(passes) / len(passes)) if passes else None,
            "passes": len(passes),
            "passes_per_min": round(len(passes) / minutes, 1),
            "shots": len(shots),
            "shots_on_target": sum(1 for _, on in shots if on),
            "xg": round(float(sum(xg for xg, _ in shots)), 2),
            "recoveries_opp_half": sum(1 for opp in recs if opp),
            "def_action_height_m": round(sum(heights) / len(heights), 1) if heights else None,
        }

    # ------------------------------------------------------------- update
    def apply(self, event: dict) -> dict:
        """Apply one event. Returns a dict of side effects detectors may use."""
        ev = dict(event)
        ev["t_s"] = event_t_s(ev)
        self.t = ev["t_s"]
        self.period = ev.get("period") or period_of(self.t)
        self._credit_live_time()
        self.events.append(ev)
        self.by_id[ev["event_id"]] = ev
        effects: dict = {"event": ev}
        kind = ev["type"]
        home = self.home

        self._track_possession(ev)

        actor = self.player(ev.get("player"), ev)
        team = ev.get("team")

        if kind == "pass":
            difficulty = pass_difficulty(ev, home)
            effects["difficulty"] = difficulty
            actor.stats["passes"] += 1
            completed = ev.get("outcome") == "complete"
            self.team_passes[team].append((self.t, completed))
            if completed:
                actor.stats["passes_completed"] += 1
                if is_progressive(ev, home):
                    actor.stats["progressive_passes"] += 1
                if (ev.get("lines_broken") or 0) >= 1:
                    actor.stats["line_breaking_passes"] += 1
                actor.add_points(P.POINTS["pass_complete_base"] + P.POINTS["pass_complete_difficulty"] * difficulty,
                                 ev["event_id"])
                pos = self._possession(ev)
                if pos is not None:
                    pos.last_complete_pass = ev
            else:
                actor.add_points(P.POINTS["pass_incomplete"] * (1 - difficulty), ev["event_id"])

        elif kind == "shot":
            xg = ev.get("xg") or 0.0
            on_target = ev.get("outcome") in ("goal", "saved")
            actor.stats["shots"] += 1
            actor.stats["xg"] = round(actor.stats["xg"] + xg, 2)
            if on_target:
                actor.stats["shots_on_target"] += 1
            self.team_shots[team].append((self.t, xg, on_target))
            points = P.POINTS["shot_base"] + P.POINTS["shot_xg"] * xg + (P.POINTS["shot_on_target"] if on_target else 0)
            if ev.get("outcome") == "goal":
                actor.stats["goals"] += 1
                points += P.POINTS["goal"]
            actor.add_points(points, ev["event_id"])
            pos = self._possession(ev)
            if pos is not None:
                last = pos.last_complete_pass
                if last and last.get("team") == team and last.get("receiver") == ev.get("player"):
                    passer = self.player(last["player"])
                    if passer:
                        passer.stats["key_passes"] += 1
                        passer.add_points(P.POINTS["key_pass"], last["event_id"])
                        effects["key_pass"] = last
                for run in pos.off_ball_runs:
                    runner = self.player(run["player"])
                    if runner is None or run.get("team") != team:
                        continue
                    bonus = P.POINTS["off_ball_run_shot"]
                    if ev.get("outcome") == "goal":
                        bonus += P.POINTS["off_ball_run_goal"] * min((run.get("space_opened_m") or 0) / 10.0, 1.0)
                    runner.add_points(bonus, run["event_id"])

        elif kind == "goal":
            score = ev.get("scoreline") or ev.get("score")
            if score:
                self.scoreline = dict(score)
            else:
                self.scoreline[self.side(team)] += 1
            self.goals.append(ev["event_id"])
            assister = self.player(ev.get("assist"))
            if assister:
                assister.stats["assists"] += 1
                assister.add_points(P.POINTS["assist"], ev["event_id"])
            effects["goal"] = ev

        elif kind == "recovery":
            opp_half = ev.get("start") is not None and in_opponent_half(ev["start"][0], team, home)
            actor.stats["recoveries"] += 1
            self.team_recoveries[team].append((self.t, opp_half, ev["event_id"]))
            points = P.POINTS["recovery"] + (P.POINTS["recovery_opp_half"] if opp_half else 0.0)
            actor.add_points(points, ev["event_id"])
            if opp_half:
                actor.stats["recoveries_opp_half"] += 1
                actor.opp_half_recovery_times.append((self.t, ev["event_id"]))
            effects["opp_half_recovery"] = opp_half
            for (pt, pteam, pname, pid) in list(self.recent_pressures):
                if pteam == team and self.t - pt <= P.COUNTERPRESS_WINDOW_S:
                    presser = self.player(pname)
                    if presser:
                        presser.add_points(P.POINTS["counterpress"], pid)
            self.recent_pressures.clear()

        elif kind in ("tackle", "duel"):
            won = ev.get("outcome") == "won"
            opponent = self.player(ev.get("opponent"))
            if kind == "tackle":
                actor.stats["tackles"] += 1
                if won:
                    actor.stats["tackles_won"] += 1
                actor.add_points(P.POINTS["tackle_won"] if won else P.POINTS["tackle_lost"], ev["event_id"])
            else:
                actor.add_points(P.POINTS["duel_won"] if won else P.POINTS["duel_lost"], ev["event_id"])
            actor.stats["duels_total"] += 1
            actor.stats["duels_won"] += 1 if won else 0
            actor.duel_streak = actor.duel_streak + 1 if won else 0
            if opponent:
                opponent.stats["duels_total"] += 1
                opponent.stats["duels_won"] += 0 if won else 1
                opponent.duel_streak = 0 if won else opponent.duel_streak + 1
                if kind == "duel":
                    opponent.add_points(P.POINTS["duel_lost"] if won else P.POINTS["duel_won"], ev["event_id"])
                winner = actor.name if won else opponent.name
                pair = self.pair_key(actor.name, opponent.name)
                if pair:
                    self.duel_pairs[pair].append((self.t, winner, ev["event_id"]))
                    effects["duel_pair"] = pair

        elif kind == "pressure":
            actor.stats["pressures"] += 1
            actor.add_points(P.POINTS["pressure"], ev["event_id"])
            self.recent_pressures.append((self.t, team, actor.name, ev["event_id"]))

        elif kind == "foul":
            actor.stats["fouls_committed"] += 1
            actor.add_points(P.POINTS["foul_committed"], ev["event_id"])
            fouled = self.player(ev.get("fouled"))
            if fouled:
                fouled.stats["fouls_received"] += 1
                fouled.add_points(P.POINTS["foul_received"], ev["event_id"])

        elif kind == "off_ball_run":
            actor.stats["off_ball_runs"] += 1
            points = P.POINTS["off_ball_run"]
            if ev.get("dragged_defender"):
                points += P.POINTS["off_ball_run_space"] * (ev.get("space_opened_m") or 0.0)
            actor.add_points(points, ev["event_id"])
            pos = self._possession(ev)
            if pos is not None:
                pos.off_ball_runs.append(ev)

        elif kind == "substitution":
            out_p = self.player(ev.get("player_out"))
            in_p = self.player(ev.get("player_in"))
            if out_p and out_p.on_since is not None:
                out_p.minutes_acc += (self.t - out_p.on_since) / 60.0
                out_p.on_since = None
            if in_p and in_p.on_since is None:
                in_p.on_since = self.t

        elif kind in ("half_time", "match_end"):
            self._close_possession()
            if kind == "match_end":
                self.finished = True

        if kind in DEF_ACTION_EVENTS and team and ev.get("start") is not None:
            self.team_def_actions[team].append((self.t, progress_from_own_goal(ev["start"][0], team, home)))

        while self.recent_pressures and self.t - self.recent_pressures[0][0] > P.COUNTERPRESS_WINDOW_S:
            self.recent_pressures.popleft()
        return effects

    def _credit_live_time(self) -> None:
        """Credit the time since the previous event to the possession in play.

        Gaps longer than LIVE_GAP_CAP_S count only up to the cap: the rest is dead
        ball (throw-ins, goal kicks, celebrations) and belongs to nobody.
        """
        if self._last_t is not None and self.current_pid is not None and self.t > self._last_t:
            gap = min(self.t - self._last_t, P.LIVE_GAP_CAP_S)
            self.possessions[self.current_pid].live.append((self._last_t, self._last_t + gap))
        self._last_t = self.t

    def pair_key(self, a: str, b: str) -> tuple[str, str] | None:
        pa, pb = self.players.get(a), self.players.get(b)
        if not pa or not pb or pa.team == pb.team:
            return None
        return (a, b) if pa.team == self.home else (b, a)

    def _possession(self, ev: dict) -> Possession | None:
        pid = ev.get("possession_id")
        return self.possessions.get(pid) if pid is not None else None

    def _close_possession(self) -> None:
        if self.current_pid is not None:
            pos = self.possessions[self.current_pid]
            if pos.end_t is None:
                pos.end_t = self.t
        self.current_pid = None

    def _track_possession(self, ev: dict) -> None:
        pid = ev.get("possession_id")
        if pid is None:
            return
        if pid not in self.possessions:
            self.possessions[pid] = Possession(pid=pid, start_t=self.t)
        pos = self.possessions[pid]
        if pid != self.current_pid:
            if self.current_pid is not None:
                prev = self.possessions[self.current_pid]
                if prev.end_t is None:
                    prev.end_t = self.t
            self.current_pid = pid
        pos.events.append(ev["event_id"])
        if pos.owner is None and ev["type"] in OWNER_EVENTS:
            pos.owner = ev.get("team")
