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
* **Carries.** A player who receives runs with the ball before his next action: 2 to 15 m
  forward with space, less near goal or against a high press, and 0 to 3 m when pressed.
  His next action starts where the carry ends. An off-ball run usually ends with the pass
  to the runner, and a dragged defender always carries his coordinates.
* **Set pieces.** A ball that goes out crosses a line: the pass ends on it with
  ``out_of_play`` and the restart is a pass with ``set_piece``: ``throw_in`` from the
  touchline, ``corner`` from the flag or ``goal_kick`` from the goal area. Kick-offs,
  free kicks after a foul and the keeper's restart after a save are set pieces too.
  Nobody presses, duels or shoots before a set piece is taken.

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
# Seed of the demo match m001: the one that keeps the whole story of the mocks (tests/test_demo_story.py).
DEMO_SEED = 1387
SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"

# Typical zone of each position for a team attacking towards +x:
# (progress from own goal in metres, y in metres). Right flank is low y.
ZONES = {
    "POR": (5.0, 34.0), "DFC": (24.0, 34.0), "LD": (36.0, 10.0), "LI": (36.0, 58.0),
    "MCD": (40.0, 34.0), "MC": (54.0, 34.0), "ED": (74.0, 10.0), "EI": (74.0, 58.0), "DC": (86.0, 34.0),
}
PAIRED_LANES = {"DFC": (26.0, 42.0), "MC": (24.0, 44.0)}
DEFAULT_STYLE = {"pass_acc": 0.80, "tempo": 1.0, "press": 0.25, "directness": 0.5}
# Rates of the possession simulator, calibrated against Premier League averages with
# ``python -m baja_insights realism`` (see docs/formulas.md, section 11).
GEN = {
    "press_win": 0.07,            # a pressure wins the ball back on the spot (before style and form)
    "tackle_attempt": 0.20,       # a pressure turns into a tackle, times the role's recover factor
    "tackle_win": 0.60,           # tackles won, before duel form
    "foul_on_lost_tackle": 0.20,  # a lost tackle is a foul
    "duel": 0.06,                 # 1 v 1 duel per step
    "shot_min_prog": 84.0,        # metres from own goal where shots start
    "shot_base": 0.05,            # per-step shot chance at shot_min_prog ...
    "shot_slope": 0.015,           # ... plus this per metre closer to goal
    "cross_shot": 0.35,           # a completed cross ends in a shot
    "foul": 0.022,                # foul suffered per step
    "backpass": 0.20,             # pass back to the goalkeeper from the own third
    "backpass_pressure": 0.20,    # extra when under pressure
    "backpass_max_prog": 38.0,
    "backpass_success": 0.97,
    "out_max_dist": 28.0,         # a misplaced pass goes out only when it ends this close to a line
    "corner_after_block": 0.35,   # a blocked shot deflected out for a corner
    "corner_after_save": 0.25,    # a save pushed out for a corner
    "corner_success": 0.40,       # a corner reaches a team-mate
    "carry_max": 15.0,            # metres a player runs with the ball before his next action, with space
    "carry_pressed_max": 3.0,     # ... and when he is pressed
    "run_gets_ball": 0.65,        # an off-ball run ends with the pass to the runner
}
# Seconds from the ball going dead to each restart
RESTART_PAUSE_S = {"throw_in": (4, 8), "goal_kick": (8, 14), "corner": (10, 16), "free_kick": (10, 20)}
# Restarts that are taken as a set piece: the first action is a pass, never a pressure, duel or shot.
SET_PIECES = ("kickoff", "throw_in", "corner", "goal_kick", "free_kick", "keeper")
# How likely each role is to be the one who presses or wins the ball back near the ball.
ROLE_FACTOR = {
    "recover": {"POR": 0.2, "DFC": 1.3, "LD": 1.1, "LI": 1.1, "MCD": 1.6, "MC": 1.0, "ED": 0.55, "EI": 0.55, "DC": 0.3},
    "press": {"POR": 0.0, "DFC": 0.4, "LD": 0.7, "LI": 0.7, "MCD": 1.0, "MC": 1.1, "ED": 1.2, "EI": 1.2, "DC": 1.3},
}


@dataclass
class Resume:
    kind: str                  # a set piece of SET_PIECES | recovery | tackle | continue
    team: str
    x: float = PITCH_LENGTH / 2
    y: float = PITCH_WIDTH / 2
    player: str | None = None
    pid: int | None = None


class MatchGenerator:
    def __init__(self, roster: Roster, seed: int = DEMO_SEED, script: dict | str | Path | None = "m001",
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
        elif r.kind == "goal_kick":
            x, y = self._to_x(5.5, team), PITCH_WIDTH / 2 + self.rng.uniform(-7.0, 7.0)
            carrier = self._pick(team, x, y, positions=("POR",))
        elif r.kind == "throw_in":
            carrier = self._pick(team, x, y, positions=("LD", "LI", "ED", "EI", "MC"))
        elif r.kind == "corner":
            carrier = self._pick(team, x, y, positions=("ED", "EI", "MC"))
        if carrier is None or carrier not in self.active[team]:
            carrier = self._pick(team, x, y, exclude=("POR",) if r.kind in ("throw_in", "corner") else ())
        set_piece = r.kind if r.kind in SET_PIECES else None
        if r.kind == "recovery":
            self._emit("recovery", team, carrier, [x, y], outcome="won", pid=pid)
            self.t += self.rng.uniform(1.0, 2.5)

        style, opp_style = self._style(team), self._style(opp)
        steps = 0
        arrival = self.t  # when the ball reached the carrier
        run_target = None  # (runner, end x, end y) of an off-ball run the next pass is for
        while True:
            if self.t + 3 > limit:
                return None if r.kind != "continue" or steps else None
            prog = self._prog(x, team)
            under = False

            # --- opponent pressure, more likely when the pressing team is high up
            press_prob = opp_style["press"] * (1.25 - prog / PITCH_LENGTH)
            if not set_piece and self.rng.random() < press_prob:
                presser = self._pick(opp, x, y, weight_key="press")
                self._emit("pressure", opp, presser, [x, y], pid=pid, target=carrier)
                under = True
                self.t += self.rng.uniform(0.5, 2.0)
                position = self.roster.players[presser].position
                if self.rng.random() < GEN["tackle_attempt"] * ROLE_FACTOR["recover"].get(position, 1.0):
                    odds = GEN["tackle_win"] * self._form(presser, "duel_win") / self._form(carrier, "duel_win")
                    won = self.rng.random() < clip(odds, 0.2, 0.85)
                    self._emit("tackle", opp, presser, [x, y], outcome="won" if won else "lost", pid=pid,
                               opponent=carrier)
                    self.t += self.rng.uniform(1.0, 2.5)
                    if won:
                        return Resume("tackle", opp, x, y, presser)
                    if self.rng.random() < GEN["foul_on_lost_tackle"]:
                        self._emit("foul", opp, presser, [x, y], pid=pid, fouled=carrier)
                        self._free_kick_pause(limit)
                        set_piece = "free_kick"
                        continue
                else:
                    win = clip(GEN["press_win"] * self._form(presser, "recover") * opp_style["press"] / 0.3,
                               0.02, 0.4)
                    if position in ("DC", "ED", "EI"):
                        win *= 0.4
                    if self.rng.random() < win:
                        self.t += self.rng.uniform(0.5, 2.0)
                        return Resume("recovery", opp, x, y, presser)
                if self.t + 3 > limit:
                    return None

            # --- the carrier runs with the ball before his next action: far with space, little when pressed
            if not set_piece:
                x, y = self._carry(team, carrier, x, y, under, opp_style, arrival)
                prog = self._prog(x, team)

            # --- 1 v 1 duel
            if not set_piece and self.rng.random() < GEN["duel"]:
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
            if not set_piece and prog >= GEN["shot_min_prog"] and \
                    self.rng.random() < GEN["shot_base"] + GEN["shot_slope"] * (prog - GEN["shot_min_prog"]):
                return self._shot(team, carrier, x, y, under, pid, cross=False)

            # --- foul suffered
            if not set_piece and self.rng.random() < GEN["foul"]:
                fouler = self._pick(opp, x, y, exclude=("POR",))
                self._emit("foul", opp, fouler, [x, y], pid=pid, fouled=carrier)
                self._free_kick_pause(limit)
                set_piece = "free_kick"
                continue

            # --- off-ball run by a teammate
            if not set_piece and prog > 62 and self.rng.random() < 0.035:
                runner = self._pick(team, x, y, positions=("ED", "EI", "DC", "MC"), exclude_names=(carrier,))
                if runner:
                    rx, ry = self._zone_xy(runner)
                    dragged = None
                    space = round(self.rng.uniform(1.0, 4.0), 1)
                    if self.rng.random() < 0.35:
                        dragged = self._pick(opp, rx, ry, positions=("DFC", "LD", "LI", "MCD"))
                        space = round(self.rng.uniform(3.0, 8.5), 1)
                    end_x = clip(rx + (8 if team == self.home else -8), 1, 104)
                    end_y = clip(ry + self.rng.gauss(0, 6), 1, 67)
                    speed = round(self.rng.uniform(22, 31), 1)
                    extra = {}
                    if dragged:  # the defender goes with the runner, goal side of him
                        back = 1.0 if team == self.home else -1.0  # towards the goal the defender protects
                        towards_centre = 1.0 if ry < PITCH_WIDTH / 2 else -1.0
                        extra = {"dragged_defender_start": [round(clip(rx + back * 4.0, 1, 104), 1),
                                                            round(clip(ry + towards_centre * 2.0, 1, 67), 1)],
                                 "dragged_defender_end": [round(clip(end_x + back * 1.5, 1, 104), 1),
                                                          round(clip(end_y + towards_centre * 1.0, 1, 67), 1)]}
                    self._emit("off_ball_run", team, runner, [rx, ry], [end_x, end_y], speed=speed, pid=pid,
                               dragged_defender=dragged, space_opened_m=space if dragged else None, **extra)
                    if self.rng.random() < GEN["run_gets_ball"]:  # the pass is for him, as he arrives
                        run_target = (runner, end_x, end_y)
                        self.t += 0.6 * distance([rx, ry], [end_x, end_y]) / (speed / 3.6)

            # --- pass
            result = self._pass(team, carrier, x, y, under, pid, style, set_piece, run_target)
            set_piece = None
            run_target = None
            steps += 1
            arrival = self.t + result["travel_s"]
            self.t += self.rng.uniform(2.5, 5.5) / style["tempo"]
            if result["outcome"] == "complete":
                carrier, x, y = result["receiver"], result["end"][0], result["end"][1]
                if result.get("cross") and self.rng.random() < GEN["cross_shot"]:
                    if self.t + 2 > limit:
                        return None
                    return self._shot(team, carrier, x, y, True, pid, cross=True)
                if steps > 16:  # a very long move ends: a shot near goal, or the rival's press finally wins it
                    if self._prog(x, team) > 70:
                        return self._shot(team, carrier, x, y, under, pid, cross=False)
                    return self._press_wins(team, carrier, x, y, pid)
            else:
                ex, ey = result["end"]
                if result["back"] or self.rng.random() < 0.50:  # a misplaced pass back goes out of play
                    # out of play only if the restart can be taken before the next scripted moment
                    restart = self._out_of_play(team, ex, ey) if self.t + 16 < limit else None
                    if restart is not None:  # the pause counts from the moment the ball went out
                        self.t = arrival + self.rng.uniform(*RESTART_PAUSE_S.get(restart.kind, (6, 14)))
                        return restart
                    return Resume("recovery", opp, ex, ey, self._pick(opp, ex, ey, weight_key="recover"))
                return Resume("recovery", opp, ex, ey, self._pick(opp, ex, ey, weight_key="recover"))

    def _free_kick_pause(self, limit: float) -> None:
        """The free kick takes 10 to 20 s, but is taken before the next scripted moment, never after it."""
        self.t = min(self.t + self.rng.uniform(*RESTART_PAUSE_S["free_kick"]), max(self.t, limit - 3.5))

    def _carry(self, team: str, carrier: str, x: float, y: float, under: bool, opp_style: dict,
               arrival: float) -> tuple[float, float]:
        """Where the carrier takes the ball before his next action. He runs at 4.5 to 6.5 m/s, using the
        time he already had since the ball reached him, and the clock moves on if he needs more."""
        prog = self._prog(x, team)
        if self.roster.players[carrier].position == "POR":
            longest = 3.0
        elif under:
            longest = GEN["carry_pressed_max"]
        else:
            room = 0.45 if prog > 75 else 0.7 if prog > 60 else 1.0
            longest = GEN["carry_max"] * room * clip(1.15 - opp_style["press"], 0.5, 1.1)
        metres = self.rng.uniform(0.0 if under else 2.0, longest)
        angle = self.rng.gauss(0.0, 0.45)
        if abs(y - PITCH_WIDTH / 2) > 24:  # near the touchline he comes inside
            angle += -0.4 if (y > PITCH_WIDTH / 2) == (team == self.home) else 0.4
        new_prog = clip(prog + metres * math.cos(angle), 2.0, 100.0)
        side = 1.0 if team == self.home else -1.0
        new_y = clip(y + side * metres * math.sin(angle), 2.0, PITCH_WIDTH - 2.0)
        need = distance([x, y], [self._to_x(new_prog, team), new_y]) / self.rng.uniform(4.5, 6.5)
        self.t += max(0.0, need - max(0.0, self.t - arrival))
        return round(self._to_x(new_prog, team), 1), round(new_y, 1)

    def _press_wins(self, team: str, carrier: str, x: float, y: float, pid: int) -> Resume:
        """The rival presses the carrier and wins the ball with a tackle, so a long move never ends in a
        turnover nobody caused."""
        opp = self.roster.opponent(team)
        presser = self._pick(opp, x, y, weight_key="press") or self._pick(opp, x, y, exclude=("POR",))
        self._emit("pressure", opp, presser, [x, y], pid=pid, target=carrier)
        self.t += self.rng.uniform(0.5, 1.5)
        self._emit("tackle", opp, presser, [x, y], outcome="won", pid=pid, opponent=carrier)
        self.t += self.rng.uniform(1.0, 2.0)
        return Resume("tackle", opp, x, y, presser)

    def _out_of_play(self, team: str, ex: float, ey: float) -> Resume | None:
        """The misplaced pass that just went out crosses the nearest line, if it ended close to one.

        Its ``end`` moves onto the line with ``out_of_play``, and the rival restarts: a throw-in from
        the touchline, a goal kick if the ball went over the goal line it attacks, or a corner if it
        went over the passer's own goal line. None when the pass ended far from every line."""
        gaps = {"bottom": ey, "top": PITCH_WIDTH - ey, "left": ex, "right": PITCH_LENGTH - ex}
        side = min(gaps, key=gaps.get)
        if gaps[side] > GEN["out_max_dist"]:
            return None
        opp = self.roster.opponent(team)
        last = self.events[-1]
        if side in ("bottom", "top"):
            point = [round(clip(ex, 1.0, PITCH_LENGTH - 1.0), 1), 0.0 if side == "bottom" else PITCH_WIDTH]
            restart = Resume("throw_in", opp, point[0], point[1])
        else:
            gx = 0.0 if side == "left" else PITCH_LENGTH
            point = [gx, round(clip(ey, 0.5, PITCH_WIDTH - 0.5), 1)]
            passer_defends_it = (gx == 0.0) == (team == self.home)  # the home team defends x = 0
            restart = self._corner_for(opp, point[1]) if passer_defends_it else Resume("goal_kick", opp)
        last["end"] = point
        last["out_of_play"] = True
        return restart

    def _corner_for(self, team: str, y: float) -> Resume:
        """Corner for ``team``, taken at the flag of the goal it attacks, on the side the ball went out."""
        gx = PITCH_LENGTH if team == self.home else 0.0
        return Resume("corner", team, gx, 0.0 if y < PITCH_WIDTH / 2 else PITCH_WIDTH)

    def _pass(self, team, carrier, x, y, under, pid, style, set_piece: str | None = None,
              run_target: tuple | None = None) -> dict:
        prog = self._prog(x, team)
        lines_form = self._form(carrier, "pass_lines")
        back = GEN["backpass"] + (GEN["backpass_pressure"] if under else 0.0)
        if run_target is not None and (run_target[0] == carrier or run_target[0] not in self.active[team]):
            run_target = None
        is_back = (set_piece not in ("throw_in", "corner", "kickoff") and run_target is None
                   and prog < GEN["backpass_max_prog"] and self.roster.players[carrier].position != "POR"
                   and self.rng.random() < back)
        if set_piece in ("throw_in", "corner", "kickoff"):
            return self._set_piece_pass(team, carrier, x, y, pid, set_piece)
        if is_back:
            dp = self.rng.uniform(4, 9) - prog  # back to the goalkeeper
            target_y = clip(34 + self.rng.gauss(0, 6), 2, 66)
        else:
            if prog > 86:
                dp = self.rng.gauss(-3, 6)
            else:
                dp = self.rng.gauss(-1 + 10 * style["directness"] * lines_form, 10)
                if prog < 20:
                    dp += 8
                if set_piece == "goal_kick":
                    dp += 12
            target_y = clip(y + self.rng.gauss(0, 14), 2, 66)
        target_p = clip(prog + dp, 2, 103)
        tx = self._to_x(target_p, team)
        exclude = () if target_p < 15 else ("POR",)
        receiver = self._pick(team, tx, target_y, weight_key="receive", exclude=exclude, exclude_names=(carrier,))
        rx, ry = self._zone_xy(receiver)
        ex = clip(0.55 * tx + 0.45 * rx + self.rng.gauss(0, 3), 0.5, 104.5)
        ey = clip(0.55 * target_y + 0.45 * ry + self.rng.gauss(0, 3), 0.5, 67.5)
        if run_target is not None:  # the pass is for the runner, where his run ends
            receiver = run_target[0]
            ex = clip(run_target[1] + self.rng.gauss(0, 1.2), 0.5, 104.5)
            ey = clip(run_target[2] + self.rng.gauss(0, 1.2), 0.5, 67.5)
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
        if is_back:  # a pass back to the keeper is almost never lost
            success = GEN["backpass_success"]
        if set_piece in ("free_kick", "keeper"):  # nobody is allowed to press the taker
            success = clip(success + 0.08, 0.3, 0.98)
        complete = self.rng.random() < success
        cross = self._prog(ex, team) >= 90 and (y < 18 or y > 50) and (ey > 20 and ey < 48)
        extra = {"receiver": receiver}
        if cross:
            extra["cross"] = True
        if set_piece:
            extra["set_piece"] = set_piece
        speed = round(clip(25 + 1.3 * dist + self.rng.gauss(0, 5), 15, 110), 1)
        self._emit("pass", team, carrier, [round(x, 1), round(y, 1)], [round(ex, 1), round(ey, 1)],
                   outcome="complete" if complete else "incomplete", speed=speed,
                   under=under, lines=lines, pid=pid, **extra)
        return {"outcome": "complete" if complete else "incomplete", "receiver": receiver,
                "end": [ex, ey], "cross": cross, "back": is_back, "travel_s": travel_time(dist, speed)}

    def _set_piece_pass(self, team, carrier, x, y, pid, set_piece: str) -> dict:
        """Throw-in, corner or kick-off: a short throw inwards, a cross into the box, a pass back."""
        prog = self._prog(x, team)
        if set_piece == "throw_in":
            inwards = 1.0 if y < PITCH_WIDTH / 2 else -1.0
            target_p = clip(prog + self.rng.gauss(2, 7), 2, 103)
            target_y = clip(y + inwards * abs(self.rng.gauss(10, 4)), 2, 66)
            success, speed = 0.92, self.rng.uniform(25, 40)
        elif set_piece == "corner":
            target_p = clip(94 + self.rng.gauss(0, 3), 88, 101)
            target_y = clip(PITCH_WIDTH / 2 + self.rng.gauss(0, 6), 24, 44)
            success, speed = GEN["corner_success"], self.rng.uniform(55, 75)
        else:  # kickoff
            target_p = clip(prog - abs(self.rng.gauss(10, 4)), 30, 52)
            target_y = clip(PITCH_WIDTH / 2 + self.rng.gauss(0, 10), 10, 58)
            success, speed = 0.97, self.rng.uniform(25, 40)
        tx = self._to_x(target_p, team)
        receiver = self._pick(team, tx, target_y, weight_key="receive", exclude=("POR",), exclude_names=(carrier,))
        ex = round(clip(tx + self.rng.gauss(0, 1.5), 0.5, 104.5), 1)
        ey = round(clip(target_y + self.rng.gauss(0, 1.5), 0.5, 67.5), 1)
        complete = self.rng.random() < success
        extra = {"receiver": receiver, "set_piece": set_piece}
        if set_piece == "corner":
            extra["cross"] = True
        self._emit("pass", team, carrier, [round(x, 1), round(y, 1)], [ex, ey],
                   outcome="complete" if complete else "incomplete", speed=round(speed, 1),
                   under=False, lines=0, pid=pid, **extra)
        return {"outcome": "complete" if complete else "incomplete", "receiver": receiver,
                "end": [ex, ey], "cross": set_piece == "corner", "back": False,
                "travel_s": travel_time(distance([x, y], [ex, ey]), speed)}

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
            if self.rng.random() < GEN["corner_after_block"]:
                self.t += self.rng.uniform(10, 16)
                return self._corner_for(team, y)
            return Resume("recovery", opp, x, y, self._pick(opp, x, y, positions=("DFC", "MCD", "LD", "LI")))
        if outcome == "saved" and self.rng.random() < GEN["corner_after_save"]:
            self.t += self.rng.uniform(10, 16)
            return self._corner_for(team, end_y)
        self.t += self.rng.uniform(4, 6) if outcome == "saved" else self.rng.uniform(*RESTART_PAUSE_S["goal_kick"])
        return Resume("keeper" if outcome == "saved" else "goal_kick", opp)

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
            if e["type"] == "pass" and e.get("start") == [PITCH_LENGTH / 2, PITCH_WIDTH / 2] and "set_piece" not in e:
                e["set_piece"] = "kickoff"  # a scripted pass from the centre spot is a kick-off
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
            kind = prev.kind if prev.kind in SET_PIECES else "continue"  # a pending set piece is still taken
            return Resume(kind, prev.team, prev.x, prev.y, prev.player, prev.pid if kind == "free_kick" else None)
        opp = self.roster.opponent(team)
        x, y = (e.get("start") or [PITCH_LENGTH / 2, PITCH_WIDTH / 2])
        if kind == "goal":
            self.t += self.rng.uniform(35, 50)
            return Resume("kickoff", opp)
        if kind == "shot":
            if e["outcome"] == "blocked":
                return Resume("recovery", opp, x, y)
            self.t += 4 if e["outcome"] == "saved" else 14
            return Resume("keeper" if e["outcome"] == "saved" else "goal_kick", opp)
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
            return Resume("free_kick", fteam, x, y, fouled, e["possession_id"])
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


def travel_time(metres: float, speed_kmh: float) -> float:
    """Seconds the ball takes to arrive, as the positions model draws it (at most 3 s)."""
    return min(metres / max(speed_kmh / 3.6, 5.0), 3.0)


def load_script(script: dict | str | Path) -> dict:
    if isinstance(script, dict):
        return script
    path = Path(script)
    if not path.suffix:
        path = SCRIPTS_DIR / f"{script}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def generate_match(roster: Roster, seed: int = DEMO_SEED, script: dict | str | Path | None = "m001",
                   match_id: str | None = None) -> list[dict]:
    """A scripted match (the demo ``m001``), or with ``script=None`` a free match where every decision
    comes from the play (``decisions.DecisionGenerator``)."""
    if script is None:
        from .decisions import DecisionGenerator
        return DecisionGenerator(roster, seed=seed, match_id=match_id).generate()
    return MatchGenerator(roster, seed=seed, script=script, match_id=match_id).generate()


__all__ = ["DEMO_SEED", "MatchGenerator", "generate_match", "load_script", "STRUCTURAL_EVENTS"]
