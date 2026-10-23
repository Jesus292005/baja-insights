"""Synthetic match generator: scripted story beats plus seeded stochastic filler.

How it works
------------
* A **script** (``scripts/m001.json``) fixes the key moments of the demo match by
  pointing at hand-written events (``mocks/events_sample.json``). Those events are
  inserted at their exact times, so the real match tells the same story as the mocks.
* Between beats a **possession simulator** plays football: passes with distance,
  pressure and lines broken, pressing that wins the ball back, flank duels, fouls,
  off-ball runs and shots valued with a small xG model.
* **Phases** (possession style, tempo, pressing) and **form** (per-player biases)
  steer the filler so the numbers agree with the story, e.g. Real Cardón keeps the
  ball in the first half and Bahía presses high after the 48th minute.
* With ``script=None`` the same simulator produces a free match whose goals are
  sampled from xG, which shows the generator is general and not a replay.

The output follows ``contracts/event.schema.json``. The same seed always gives the
same match.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

from ..contract import (
    HALF_LENGTH_S, MATCH_LENGTH_S, PITCH_LENGTH, PITCH_WIDTH, STRUCTURAL_EVENTS, clip, distance,
    event_t_s, parse_clock,
)
from ..roster import Player, Roster
from .xg import expected_goals

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"

# Typical zone of each position for a team attacking towards +x:
# (progress from own goal in metres, y in metres). Right flank is low y.
ZONES = {
    "POR": (5.0, 34.0), "DFC": (24.0, 34.0), "LD": (36.0, 10.0), "LI": (36.0, 58.0),
    "MCD": (40.0, 34.0), "MC": (54.0, 34.0), "ED": (74.0, 10.0), "EI": (74.0, 58.0), "DC": (86.0, 34.0),
}
PAIRED_LANES = {"DFC": (26.0, 42.0), "MC": (24.0, 44.0)}
DEFAULT_STYLE = {"pass_acc": 0.80, "tempo": 1.0, "press": 0.25, "directness": 0.5}
# How likely each role is to be the one who presses or wins the ball back near the ball.
ROLE_FACTOR = {
    "recover": {"POR": 0.2, "DFC": 1.3, "LD": 1.1, "LI": 1.1, "MCD": 1.6, "MC": 1.0, "ED": 0.55, "EI": 0.55, "DC": 0.3},
    "press": {"POR": 0.0, "DFC": 0.4, "LD": 0.7, "LI": 0.7, "MCD": 1.0, "MC": 1.1, "ED": 1.2, "EI": 1.2, "DC": 1.3},
}


@dataclass
class Resume:
    kind: str                  # kickoff | keeper | recovery | restart | continue
    team: str
    x: float = PITCH_LENGTH / 2
    y: float = PITCH_WIDTH / 2
    player: str | None = None
    pid: int | None = None


class MatchGenerator:
    def __init__(self, roster: Roster, seed: int = 23, script: dict | str | Path | None = "m001",
                 match_id: str | None = None):
        self.roster = roster
        self.rng = random.Random(seed)
        self.seed = seed
        self.script = load_script(script) if script is not None else None
        self.match_id = match_id or (self.script or {}).get("match_id") or roster.match.get("match_id", "m001")
        self.home, self.away = roster.home, roster.away
        self.events: list[dict] = []
        self.t = 0.0
        self.period = 1
        self.scoreline = {"home": 0, "away": 0}
        self._next_id = 1
        self._next_pid = 1
        self.current: tuple[str, int] | None = None
        self.active = {team: {p.name for p in roster.team_players(team, starters_only=True)}
                       for team in (self.home, self.away)}
        self.lanes = self._assign_lanes()
        self.lock = bool(self.script and self.script.get("lock_scoreline"))
        self.beats = self._load_beats() if self.script else []
        self.phases = [self._parse_window(p) for p in (self.script or {}).get("phases", [])]
        self.form = [self._parse_window(f) for f in (self.script or {}).get("form", [])]

    # ================================================================ public
    def generate(self) -> list[dict]:
        self._emit("match_start", None, None, None, home=self.home, away=self.away)
        first = self.home
        if self.beats and self.beats[0]["start"] <= 2:
            beat = self.beats.pop(0)
            resume = self._insert_beat(beat)
        else:
            resume = Resume("kickoff", first)
        self._run_period(1, HALF_LENGTH_S, resume)
        self.t = HALF_LENGTH_S
        self._emit("half_time", None, None, None, scoreline=dict(self.scoreline))
        self.period = 2
        self._emit("second_half_start", None, None, None)
        self._run_period(2, MATCH_LENGTH_S, Resume("kickoff", self.roster.opponent(first)))
        self.t = MATCH_LENGTH_S
        self._emit("match_end", None, None, None, scoreline=dict(self.scoreline))
        return self.events

    # ============================================================== periods
    def _run_period(self, period: int, end_t: int, resume: Resume) -> None:
        self.period = period
        while self.t < end_t - 4:
            beat = self.beats[0] if self.beats and self.beats[0]["start"] < end_t else None
            if beat is None and not self.lock:
                self._maybe_free_substitution()
            limit = (beat["start"] - 2) if beat else end_t - 3
            while self.t < limit - 4:
                nxt = self._possession(resume, limit)
                if nxt is None:
                    break
                resume = nxt
            if beat is None:
                break
            self.beats.pop(0)
            self.t = max(self.t, beat["start"])
            resume = self._insert_beat(beat, resume)

    # ============================================================ possession
    def _possession(self, r: Resume, limit: float) -> Resume | None:
        team, opp = r.team, self.roster.opponent(r.team)
        pid = r.pid or self._new_pid()
        self.current = (team, pid)
        x, y = r.x, r.y
        carrier = r.player
        if r.kind == "kickoff":
            x, y = PITCH_LENGTH / 2, PITCH_WIDTH / 2
            carrier = self._pick(team, x, y, positions=("DC",)) or self._pick(team, x, y)
        elif r.kind == "keeper":
            x, y = self._to_x(6.0, team), PITCH_WIDTH / 2
            carrier = self._pick(team, x, y, positions=("POR",))
        if carrier is None or carrier not in self.active[team]:
            carrier = self._pick(team, x, y)
        if r.kind == "recovery":
            self._emit("recovery", team, carrier, [x, y], outcome="won", pid=pid)
            self.t += self.rng.uniform(1.0, 2.5)

        style, opp_style = self._style(team), self._style(opp)
        steps = 0
        while True:
            if self.t + 3 > limit:
                return None if r.kind != "continue" or steps else None
            prog = self._prog(x, team)
            under = False

            # --- opponent pressure, more likely when the pressing team is high up
            press_prob = opp_style["press"] * (1.25 - prog / PITCH_LENGTH)
            if self.rng.random() < press_prob:
                presser = self._pick(opp, x, y, weight_key="press")
                self._emit("pressure", opp, presser, [x, y], pid=pid, target=carrier)
                under = True
                self.t += self.rng.uniform(0.5, 2.0)
                win = clip(0.07 * self._form(presser, "recover") * opp_style["press"] / 0.3, 0.02, 0.4)
                if self.roster.players[presser].position in ("DC", "ED", "EI"):
                    win *= 0.4
                if self.rng.random() < win:
                    self.t += self.rng.uniform(0.5, 2.0)
                    return Resume("recovery", opp, x, y, presser)
                if self.t + 3 > limit:
                    return None

            # --- 1 v 1 duel
            if self.rng.random() < 0.06:
                defender = self._pick(opp, x, y, weight_key="duel", exclude=("POR",))
                fa, fd = self._form(carrier, "duel_win"), self._form(defender, "duel_win")
                attacker_wins = self.rng.random() < fa / (fa + fd)
                winner, loser = (carrier, defender) if attacker_wins else (defender, carrier)
                winner_team = team if attacker_wins else opp
                self._emit("duel", winner_team, winner, [x, y], outcome="won", pid=pid, opponent=loser)
                self.t += self.rng.uniform(1.0, 2.5)
                if not attacker_wins:
                    return Resume("recovery", opp, x, y, defender)

            # --- shot
            if prog >= 83 and self.rng.random() < 0.07 + 0.015 * (prog - 83):
                return self._shot(team, carrier, x, y, under, pid, cross=False)

            # --- foul suffered
            if self.rng.random() < 0.012:
                fouler = self._pick(opp, x, y, exclude=("POR",))
                self._emit("foul", opp, fouler, [x, y], pid=pid, fouled=carrier)
                self.t += self.rng.uniform(12, 25)
                under = False
                if self.t + 3 > limit:
                    return None

            # --- off-ball run by a teammate
            if prog > 62 and self.rng.random() < 0.035:
                runner = self._pick(team, x, y, positions=("ED", "EI", "DC", "MC"), exclude_names=(carrier,))
                if runner:
                    rx, ry = self._zone_xy(runner)
                    dragged = None
                    space = round(self.rng.uniform(1.0, 4.0), 1)
                    if self.rng.random() < 0.35:
                        dragged = self._pick(opp, rx, ry, positions=("DFC", "LD", "LI", "MCD"))
                        space = round(self.rng.uniform(3.0, 8.5), 1)
                    end_x = clip(rx + (8 if team == self.home else -8), 1, 104)
                    self._emit("off_ball_run", team, runner, [rx, ry], [end_x, clip(ry + self.rng.gauss(0, 6), 1, 67)],
                               speed=round(self.rng.uniform(22, 31), 1), pid=pid, dragged_defender=dragged,
                               space_opened_m=space if dragged else None)

            # --- pass
            result = self._pass(team, carrier, x, y, under, pid, style)
            steps += 1
            self.t += self.rng.uniform(2.5, 5.5) / style["tempo"]
            if result["outcome"] == "complete":
                carrier, x, y = result["receiver"], result["end"][0], result["end"][1]
                if result.get("cross") and self.rng.random() < 0.35:
                    if self.t + 2 > limit:
                        return None
                    return self._shot(team, carrier, x, y, True, pid, cross=True)
                if steps > 16:
                    return self._shot(team, carrier, x, y, under, pid, cross=False) \
                        if self._prog(x, team) > 70 else Resume("recovery", opp, x, y)
            else:
                ex, ey = result["end"]
                if self.rng.random() < 0.50:
                    self.t += self.rng.uniform(6, 14)
                    return Resume("restart", opp, ex, ey)
                return Resume("recovery", opp, ex, ey, self._pick(opp, ex, ey, weight_key="recover"))

    def _pass(self, team, carrier, x, y, under, pid, style) -> dict:
        prog = self._prog(x, team)
        lines_form = self._form(carrier, "pass_lines")
        if prog > 86:
            dp = self.rng.gauss(-3, 6)
        else:
            dp = self.rng.gauss(-1 + 10 * style["directness"] * lines_form, 10)
            if prog < 20:
                dp += 8
        target_p = clip(prog + dp, 2, 103)
        target_y = clip(y + self.rng.gauss(0, 14), 2, 66)
        tx = self._to_x(target_p, team)
        exclude = () if target_p < 15 else ("POR",)
        receiver = self._pick(team, tx, target_y, weight_key="receive", exclude=exclude, exclude_names=(carrier,))
        rx, ry = self._zone_xy(receiver)
        ex = clip(0.55 * tx + 0.45 * rx + self.rng.gauss(0, 3), 0.5, 104.5)
        ey = clip(0.55 * target_y + 0.45 * ry + self.rng.gauss(0, 3), 0.5, 67.5)
        progress = self._prog(ex, team) - prog
        lines = 0
        if progress >= 22:
            roll = self.rng.random()
            lines = 2 if roll < min(0.30 * lines_form, 0.9) else (1 if roll < min(0.65 * lines_form, 0.95) else 0)
        elif progress >= 14:
            lines = 1 if self.rng.random() < min(0.25 * lines_form, 0.9) else 0
        dist = distance([x, y], [ex, ey])
        hard = (0.3 * min(dist / 40, 1) + 0.25 * under + 0.25 * min(lines / 2, 1)
                + 0.2 * clip(progress / 30, 0, 1))
        success = clip(style["pass_acc"] + 0.10 - 0.35 * hard, 0.3, 0.98)
        complete = self.rng.random() < success
        cross = self._prog(ex, team) >= 90 and (y < 18 or y > 50) and (ey > 20 and ey < 48)
        extra = {"receiver": receiver}
        if cross:
            extra["cross"] = True
        self._emit("pass", team, carrier, [round(x, 1), round(y, 1)], [round(ex, 1), round(ey, 1)],
                   outcome="complete" if complete else "incomplete",
                   speed=round(clip(25 + 1.3 * dist + self.rng.gauss(0, 5), 15, 110), 1),
                   under=under, lines=lines, pid=pid, **extra)
        return {"outcome": "complete" if complete else "incomplete", "receiver": receiver,
                "end": [ex, ey], "cross": cross}

    def _shot(self, team, shooter, x, y, under, pid, cross) -> Resume:
        opp = self.roster.opponent(team)
        prog = self._prog(x, team)
        xg = expected_goals(prog, y, under, cross)
        on_target = self.rng.random() < 0.30 + 0.5 * xg
        if not self.lock and self.rng.random() < xg:
            outcome = "goal"
        elif on_target:
            outcome = "saved"
        else:
            outcome = "blocked" if self.rng.random() < 0.3 else "off_target"
        goal_x = PITCH_LENGTH if team == self.home else 0.0
        end_y = clip(34 + self.rng.gauss(0, 2.5 if outcome in ("goal", "saved") else 7), 0, 68)
        if outcome == "off_target" and abs(end_y - 34) < 4:
            end_y = 34 + (5 if end_y >= 34 else -5)
        end = [goal_x, round(end_y, 1)] if outcome != "blocked" else [round(clip(x + (3 if team == self.home else -3), 0, 105), 1), round(y, 1)]
        self._emit("shot", team, shooter, [round(x, 1), round(y, 1)], end, outcome=outcome,
                   speed=round(clip(self.rng.gauss(94, 9), 60, 124), 1), under=under, pid=pid, xg=xg)
        if outcome == "goal":
            side = "home" if team == self.home else "away"
            self.scoreline[side] += 1
            self._emit("goal", team, shooter, [round(x, 1), round(y, 1)], pid=pid,
                       assist=self._last_passer(pid, shooter), scoreline=dict(self.scoreline))
            self.t += self.rng.uniform(35, 50)
            return Resume("kickoff", opp)
        if outcome == "blocked":
            self.t += self.rng.uniform(1, 2)
            return Resume("recovery", opp, x, y, self._pick(opp, x, y, positions=("DFC", "MCD", "LD", "LI")))
        self.t += self.rng.uniform(4, 6) if outcome == "saved" else self.rng.uniform(12, 20)
        return Resume("keeper", opp)

    # ================================================================ beats
    def _load_beats(self) -> list[dict]:
        source = self.script.get("beats_source")
        path = Path(source)
        if not path.is_absolute():
            path = REPO_ROOT / source
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw = [e for e in raw if e["type"] not in ("match_start", "half_time", "second_half_start", "match_end")]
        raw.sort(key=lambda e: (event_t_s(e), e["event_id"]))
        beats: list[list[dict]] = []
        for e in raw:
            if beats and e["type"] != "substitution" and beats[-1][-1]["type"] != "substitution":
                last = beats[-1][-1]
                same_pid = e.get("possession_id") is not None and e.get("possession_id") == last.get("possession_id")
                if same_pid or event_t_s(e) - event_t_s(last) <= 8:
                    beats[-1].append(e)
                    continue
            beats.append([e])
        return [{"start": event_t_s(b[0]), "end": event_t_s(b[-1]), "events": b} for b in beats]

    def _insert_beat(self, beat: dict, before: Resume | None = None) -> Resume:
        pid_map: dict[int, int] = {}
        last = None
        for src in beat["events"]:
            e = dict(src)
            old_pid = e.get("possession_id")
            if old_pid is not None and old_pid not in pid_map:
                defensive = e["type"] in ("pressure", "tackle", "foul")
                if defensive and self.current and self.current[0] != e.get("team"):
                    pid_map[old_pid] = self.current[1]
                else:
                    pid_map[old_pid] = self._new_pid()
            e["possession_id"] = pid_map.get(old_pid) if old_pid is not None else None
            self.t = max(self.t, event_t_s(src))
            e.pop("score", None)
            if src.get("score") and "scoreline" not in e:
                e["scoreline"] = src["score"]
            if e["type"] == "goal":
                side = "home" if e["team"] == self.home else "away"
                self.scoreline[side] += 1
                e["scoreline"] = dict(self.scoreline)
            if e["type"] == "substitution":
                self.active[e["team"]].discard(e["player_out"])
                self.active[e["team"]].add(e["player_in"])
            self._append(e)
            last = e
            if e.get("possession_id") is not None and e["type"] not in ("pressure", "tackle", "foul"):
                self.current = (e["team"], e["possession_id"])
        self.t += 1
        return self._resume_after(last, before)

    def _resume_after(self, e: dict, before: Resume | None) -> Resume:
        team = e.get("team")
        kind = e["type"]
        if kind == "substitution":
            prev = before or Resume("kickoff", self.home)
            return Resume("continue", prev.team, prev.x, prev.y, prev.player, None)
        opp = self.roster.opponent(team)
        x, y = (e.get("start") or [PITCH_LENGTH / 2, PITCH_WIDTH / 2])
        if kind == "goal":
            self.t += self.rng.uniform(35, 50)
            return Resume("kickoff", opp)
        if kind == "shot":
            if e["outcome"] == "blocked":
                return Resume("recovery", opp, x, y)
            self.t += 4 if e["outcome"] == "saved" else 14
            return Resume("keeper", opp)
        if kind == "pass":
            ex, ey = e["end"]
            if e["outcome"] == "complete":
                return Resume("continue", team, ex, ey, e.get("receiver"), e["possession_id"])
            return Resume("recovery", opp, ex, ey)
        if kind in ("recovery", "off_ball_run"):
            return Resume("continue", team, x, y, e["player"] if kind == "recovery" else None, e["possession_id"])
        if kind in ("duel", "tackle"):
            if e.get("outcome") == "won" and self._prog(x, team) < PITCH_LENGTH / 2:
                return Resume("recovery", team, x, y, e["player"])
            return Resume("continue", team, x, y, e["player"], e["possession_id"])
        if kind == "foul":
            self.t += 18
            fouled = e.get("fouled")
            fteam = self.roster.players[fouled].team if fouled in self.roster.players else opp
            return Resume("continue", fteam, x, y, fouled, e["possession_id"])
        if kind == "pressure":
            return Resume("continue", opp, x, y, e.get("target"), e["possession_id"])
        return Resume("kickoff", opp)

    # ============================================================== helpers
    def _emit(self, kind, team, player, start, end=None, outcome=None, speed=None, under=False,
              lines=0, pid=None, **extra) -> dict:
        position = self.roster.players[player].position if player in self.roster.players else None
        e = {
            "match_id": self.match_id, "event_id": None, "period": self.period,
            "minute": None, "second": None, "t_s": None, "type": kind, "team": team, "player": player,
            "position": position, "start": start, "end": end, "outcome": outcome, "speed_kmh": speed,
            "under_pressure": bool(under), "lines_broken": int(lines), "possession_id": pid,
        }
        e.update(extra)
        self._append(e)
        return e

    def _append(self, e: dict) -> None:
        t = int(min(self.t, MATCH_LENGTH_S))
        if self.events:
            t = max(t, self.events[-1]["t_s"])
        e["event_id"] = self._next_id
        self._next_id += 1
        e["t_s"] = t
        e["minute"], e["second"] = divmod(t, 60)
        e["period"] = self.period
        e["match_id"] = self.match_id
        for key in ("start", "end"):
            if e.get(key) is not None:
                e[key] = [round(clip(e[key][0], 0, PITCH_LENGTH), 1), round(clip(e[key][1], 0, PITCH_WIDTH), 1)]
        self.events.append(e)

    def _new_pid(self) -> int:
        pid = self._next_pid
        self._next_pid += 1
        return pid

    def _prog(self, x: float, team: str) -> float:
        return x if team == self.home else PITCH_LENGTH - x

    def _to_x(self, prog: float, team: str) -> float:
        return prog if team == self.home else PITCH_LENGTH - prog

    def _assign_lanes(self) -> dict[str, tuple[float, float]]:
        lanes = {}
        for team in (self.home, self.away):
            seen: dict[str, int] = {}
            for p in self.roster.team_players(team):
                prog, y = ZONES.get(p.position, ZONES["MC"])
                if p.position in PAIRED_LANES and p.starter:
                    idx = seen.get(p.position, 0)
                    seen[p.position] = idx + 1
                    y = PAIRED_LANES[p.position][idx % 2]
                if team != self.home:
                    y = PITCH_WIDTH - y
                lanes[p.name] = (prog, y)
        return lanes

    def _zone_xy(self, name: str) -> tuple[float, float]:
        player = self.roster.players[name]
        prog, y = self.lanes[name]
        return self._to_x(prog, player.team), y

    def _pick(self, team: str, x: float, y: float, weight_key: str | None = None,
              positions: tuple[str, ...] | None = None, exclude: tuple[str, ...] = (),
              exclude_names: tuple[str | None, ...] = ()) -> str | None:
        names, weights = [], []
        for name in sorted(self.active[team]):
            player: Player = self.roster.players[name]
            if positions and player.position not in positions:
                continue
            if player.position in exclude or name in exclude_names:
                continue
            px, py = self._zone_xy(name)
            w = math.exp(-((px - x) / 22.0) ** 2 - ((py - y) / 18.0) ** 2) + 1e-3
            if weight_key:
                w *= self._form(name, weight_key) * ROLE_FACTOR.get(weight_key, {}).get(player.position, 1.0)
            names.append(name)
            weights.append(w)
        if not names:
            return None
        return self.rng.choices(names, weights=weights, k=1)[0]

    def _form(self, name: str | None, key: str) -> float:
        value = 1.0
        for f in self.form:
            if f.get("player") == name and f["from"] <= self.t < f["to"] and key in f:
                value *= float(f[key])
        return value

    def _style(self, team: str) -> dict:
        style = dict(DEFAULT_STYLE)
        for p in self.phases:
            if p.get("team") == team and p["from"] <= self.t < p["to"]:
                style.update({k: v for k, v in p.items() if k in DEFAULT_STYLE})
        return style

    @staticmethod
    def _parse_window(entry: dict) -> dict:
        out = dict(entry)
        out["from"] = parse_clock(entry.get("from", "00:00"))
        out["to"] = parse_clock(entry.get("to", "90:00")) if entry.get("to") not in (None, "90:00") else MATCH_LENGTH_S + 1
        return out

    def _last_passer(self, pid: int, shooter: str) -> str | None:
        for e in reversed(self.events):
            if e.get("possession_id") != pid:
                break
            if e["type"] == "pass" and e.get("outcome") == "complete" and e.get("receiver") == shooter:
                return e["player"]
        return None

    def _maybe_free_substitution(self) -> None:
        """Free mode only: two changes per team between 60' and 80'."""
        if not hasattr(self, "_free_subs"):
            self._free_subs = []
            for team in (self.home, self.away):
                bench = [p for p in self.roster.team_players(team) if not p.starter]
                for i, sub in enumerate(bench[:2]):
                    outs = [p.name for p in self.roster.team_players(team, True) if p.position == sub.position]
                    if outs:
                        at = 60 * 60 + self.rng.randint(0, 20 * 60)
                        self.beats.append({"start": at, "end": at, "events": [{
                            "match_id": self.match_id, "event_id": 0, "period": 2, "minute": at // 60,
                            "second": at % 60, "t_s": at, "type": "substitution", "team": team, "player": None,
                            "position": None, "start": None, "end": None, "outcome": None, "speed_kmh": None,
                            "under_pressure": False, "lines_broken": 0, "possession_id": None,
                            "player_out": outs[0], "player_in": sub.name}]})
            self.beats.sort(key=lambda b: b["start"])


def load_script(script: dict | str | Path) -> dict:
    if isinstance(script, dict):
        return script
    path = Path(script)
    if not path.suffix:
        path = SCRIPTS_DIR / f"{script}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def generate_match(roster: Roster, seed: int = 23, script: dict | str | Path | None = "m001",
                   match_id: str | None = None) -> list[dict]:
    return MatchGenerator(roster, seed=seed, script=script, match_id=match_id).generate()


__all__ = ["MatchGenerator", "generate_match", "load_script", "STRUCTURAL_EVENTS"]
