"""Illustrative positions of the 22 players and the ball, 2 frames per second.

The events only say where the player on the ball is. Everybody else is placed by a
deterministic model, so the pitch can show the whole team without inventing what the
events say:

1. **Shape.** Each player has the zone of his position that the generator already uses
   to pick who makes each action (``generator.simulate.ZONES``). The block follows the
   ball, opens up with the ball and closes down without it. How high it defends comes
   from the pressing of the script's phases, so Bahía's high press after the 48th
   minute (the ``pressure_shift`` insight) is visible.
2. **Anchors.** Every event pins its players to its coordinates and second: the player
   on the ball, the receiver at the end of a completed pass, the runner and the dragged
   defender of an off-ball run, the keeper on a save, and the rival in a duel, tackle,
   pressure or foul. A player heads straight for his next anchor in the seconds before it.
3. **Set pieces.** While the ball is out (between the event that stops play and the pass
   with ``set_piece`` that restarts it) both teams take up the shape of the restart:
   kick-off, throw-in, corner, goal kick, free kick with a wall, or the keeper's restart.
4. **Movement.** Speed is capped (8.5 m/s in play, 6.5 m/s while the ball is out) and
   players keep 1.5 m apart unless they are in the same action.

Coordinates are the events' ones: metres on 105 x 68, origin at the bottom left, the home
team attacking x = 105 in both halves. The teams change ends at half time on screen: the
interface rotates everything it draws in the second half, ``(105 - x, 68 - y)``, as the
``periods`` field says.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field

from ..contract import HALF_LENGTH_S, MATCH_LENGTH_S, PITCH_LENGTH, PITCH_WIDTH, clip
from ..generator.simulate import DEFAULT_STYLE, MatchGenerator, load_script
from ..roster import Roster

HZ = 2
DT = 1.0 / HZ
V_PLAY = 8.5          # m/s, top speed in play
V_DEAD = 6.5          # m/s, jogging into place while the ball is out
V_CRUISE = 6.0        # m/s, drifting with the shape when no anchor is near
ANCHOR_WINDOW_S = 6.0  # a player heads for an anchor this long before it
SECOND_WINDOW_S = 3.0  # ... or this long for the rival in a duel, pressure, tackle or foul
ANTICIPATION_S = 1.5   # a receiver starts towards the pass this long before it is played, never earlier
BALL_AT_FOOT_M = 0.7   # the ball runs this far ahead of the player who carries it
SWAY_M = 0.8           # how far a player drifts around his spot in the shape
TEAMMATE_GAP_M = 4.0   # team-mates keep the width of a disc on screen (3.6 m) between them, with margin
PRESS_GAP_M = (3.5, 5.0)  # the nearest rival closes the carrier to this distance, closer with a high press
COVER_GAP_M = 9.0      # the second rival covers behind him, on the line to his goal
MARK_GAP_M = 1.8       # a defender tracks a runner this close, goal side
SUPPORT_M = (6.0, 10.0)  # two team-mates offer a pass: one behind and wide, one ahead on the other side
SHAPE_LAG_S = 1.6      # time constant of the drift towards the shape
MIN_GAP_M = 1.5
FREE_KICK_GAP_M = 9.15
# How far the rivals stand from the ball until a set piece is taken
RIVAL_GAP = {"free_kick": FREE_KICK_GAP_M, "corner": FREE_KICK_GAP_M, "kickoff": FREE_KICK_GAP_M, "throw_in": 2.0}
SLOT_ORDER = ("POR", "LD", "DFC", "LI", "MCD", "MC", "ED", "EI", "DC")
DEFENSIVE_ACTIONS = ("pressure", "tackle", "foul")
P_ACTOR, P_LINK, P_SECOND = 3, 2, 1


@dataclass
class Anchor:
    t: float
    x: float
    y: float
    priority: int
    window: float = ANCHOR_WINDOW_S
    release: float | None = None  # the second the player can know about it: he does not move before


@dataclass
class DeadBall:
    """Play stopped from ``start`` to ``end``, when ``taker`` restarts with ``kind`` at ``spot``."""
    start: float
    end: float
    kind: str
    team: str
    taker: str
    spot: tuple[float, float]
    out_at: tuple[float, float] | None = None


@dataclass
class Timeline:
    anchors: dict[str, list[Anchor]] = field(default_factory=dict)
    ball_keys: list[tuple[float, float, float]] = field(default_factory=list)  # (t, x, y)
    holders: list[tuple[float, float, str]] = field(default_factory=list)     # (from, to, player)
    possession: list[tuple[float, str]] = field(default_factory=list)          # (from, team)
    dead: list[DeadBall] = field(default_factory=list)
    runs: list[tuple[float, float, str, str, bool]] = field(default_factory=list)  # (from, to, runner, team, marked)


# ---------------------------------------------------------------- geometry
def prog_of(x: float, team: str, home: str) -> float:
    return x if team == home else PITCH_LENGTH - x


def x_of(prog: float, team: str, home: str) -> float:
    return prog if team == home else PITCH_LENGTH - prog


def travel_s(start, end, speed_kmh) -> float:
    if start is None or end is None:
        return 0.0
    v = max((speed_kmh or 50.0) / 3.6, 5.0)
    return min(math.dist(start, end) / v, 3.0)


def toward_own_goal(point, team: str, home: str, metres: float) -> tuple[float, float]:
    x, y = point
    return (clip(x - metres if team == home else x + metres, 0.0, PITCH_LENGTH), y)


def clamp_pitch(x: float, y: float, margin: float = 0.5) -> tuple[float, float]:
    return clip(x, margin, PITCH_LENGTH - margin), clip(y, margin, PITCH_WIDTH - margin)


# ---------------------------------------------------------------- the model
class PositionModel:
    def __init__(self, events: list[dict], roster: Roster, script: str | dict | None = None):
        self.events = [e for e in events]
        self.roster = roster
        self.home, self.away = roster.home, roster.away
        self.match_id = next((e["match_id"] for e in events if e.get("match_id")), "m001")
        generator = MatchGenerator(roster, script=None)
        self.lanes: dict[str, tuple[float, float]] = generator.lanes  # (progress from own goal, y)
        self.phases = [MatchGenerator._parse_window(p) for p in (load_script(script).get("phases", []) if script else [])]
        self.lineups, self.changes = self._lineups()
        self.timeline = self._timeline()

    # ------------------------------------------------------------ lineups
    def _lineups(self):
        lineups = {}
        for team in (self.home, self.away):
            starters = self.roster.team_players(team, starters_only=True)
            order = {p: i for i, p in enumerate(SLOT_ORDER)}
            starters.sort(key=lambda p: (order.get(p.position, 99), -self.lanes[p.name][1] if team == self.home else self.lanes[p.name][1]))
            lineups[team] = [p.name for p in starters]
        changes = []
        current = {team: list(names) for team, names in lineups.items()}
        for e in self.events:
            if e["type"] == "substitution":
                slot = current[e["team"]].index(e["player_out"])
                current[e["team"]][slot] = e["player_in"]
                changes.append({"t_s": e["t_s"], "team": "home" if e["team"] == self.home else "away", "slot": slot,
                                "player_out": e["player_out"], "player_in": e["player_in"]})
        return lineups, changes

    def on_pitch(self, team: str, t: float) -> list[str]:
        names = list(self.lineups[team])
        side = "home" if team == self.home else "away"
        for c in self.changes:
            if c["team"] == side and c["t_s"] <= t:
                names[c["slot"]] = c["player_in"]
        return names

    # ------------------------------------------------------------ timeline
    def _timeline(self) -> Timeline:
        tl = Timeline()
        anchors: dict[str, list[Anchor]] = {name: [] for name in self.roster.players}
        add = lambda name, t, p, pr, w=ANCHOR_WINDOW_S, release=None: name in anchors and p is not None and \
            anchors[name].append(Anchor(float(t), *clamp_pitch(p[0], p[1], 0.0), pr, w, release))
        play = [e for e in self.events if e.get("start") is not None and e.get("team")]
        ball = tl.ball_keys
        last_end_t = 0.0
        for i, e in enumerate(play):
            t, team, start = float(e["t_s"]), e["team"], e["start"]
            kind = e["type"]
            nxt = play[i + 1] if i + 1 < len(play) else None
            # --- possession
            owner = team if kind not in DEFENSIVE_ACTIONS or (kind == "tackle" and e.get("outcome") == "won") \
                else self.roster.opponent(team)
            if not tl.possession or tl.possession[-1][1] != owner:
                tl.possession.append((t, owner))
            # --- set piece: the dead ball before it
            if e.get("set_piece"):
                prev = play[i - 1] if i > 0 else None
                out_at = None
                if prev is not None and prev.get("out_of_play"):
                    out_at = tuple(prev["end"])  # over the touchline or the goal line
                elif prev is not None and prev["type"] == "shot" and prev.get("outcome") == "off_target":
                    out_at = tuple(prev["end"])  # wide of the post
                elif prev is not None and prev["type"] == "shot" and e["set_piece"] == "corner":
                    out_at = (start[0], 34.0 + (6.0 if start[1] > 34 else -6.0))  # deflected over the line
                elif prev is not None and prev["type"] == "goal":
                    out_at = "net"
                begin = min(max(last_end_t, t - 40.0), t)
                if e["set_piece"] == "kickoff" and t in (0.0, float(HALF_LENGTH_S)):
                    begin = t
                tl.dead.append(DeadBall(begin, t, e["set_piece"], team, e["player"], tuple(start), out_at))
            # --- anchors. Nobody heads for an action before he can read it: the receiver when the pass
            # is about to be played, the rival when the ball reaches his zone.
            prev = play[i - 1] if i > 0 else None
            release = t - ANCHOR_WINDOW_S
            if prev is not None and prev["type"] == "pass" and prev.get("receiver") == e["player"] \
                    and prev.get("outcome") == "complete":
                release = prev["t_s"] - ANTICIPATION_S
            elif prev is not None and prev["type"] == "pass" and prev.get("outcome") == "incomplete":
                release = prev["t_s"] - 0.5  # reads the misplaced pass
            elif prev is not None and prev["type"] == "shot":
                release = float(prev["t_s"])
            elif prev is not None and (kind in DEFENSIVE_ACTIONS or kind == "duel"):
                release = max(prev["t_s"] - 1.0, t - ANCHOR_WINDOW_S)
            release = min(release, t)
            if kind == "off_ball_run":
                # the run lasts until the ball is played (the pass it was made for), at most 10 s
                dt = math.dist(start, e["end"]) / ((e.get("speed_kmh") or 25) / 3.6)
                played = next((n for n in play[i + 1:] if n["type"] in ("pass", "shot")), None)
                if played is not None and played["team"] == team and 0 < played["t_s"] - t <= 10:
                    dt = max(dt, float(played["t_s"] - t))
                add(e["player"], t, start, P_LINK, release=t - 2.0)
                add(e["player"], t + dt, e["end"], P_LINK, release=t)
                tl.runs.append((t, t + dt, e["player"], team, bool(e.get("dragged_defender_end"))))
                if e.get("dragged_defender_start") and e.get("dragged_defender_end"):
                    add(e["dragged_defender"], t, e["dragged_defender_start"], P_LINK, release=t - 2.0)
                    add(e["dragged_defender"], t + dt, e["dragged_defender_end"], P_LINK, release=t)
                continue
            if kind in DEFENSIVE_ACTIONS:
                add(e["player"], t, toward_own_goal(start, team, self.home, 1.0), P_ACTOR, release=release)
                other = e.get("target") or e.get("opponent") or e.get("fouled")
                if other in self.roster.players:
                    add(other, t, start, P_SECOND, SECOND_WINDOW_S)
            else:
                add(e["player"], t, start, P_ACTOR, release=release)
                if kind == "duel" and e.get("opponent") in self.roster.players:
                    loser_team = self.roster.players[e["opponent"]].team
                    add(e["opponent"], t, toward_own_goal(start, loser_team, self.home, 1.0), P_SECOND, SECOND_WINDOW_S)
            if kind == "goal":
                continue
            # --- the ball
            ball.append((t, float(start[0]), float(start[1])))
            last_end_t = t + 1.0
            if kind in ("pass", "shot") and e.get("end") is not None:
                arrive = t + travel_s(start, e["end"], e.get("speed_kmh"))
                end = e["end"]
                ball.append((arrive, float(end[0]), float(end[1])))
                last_end_t = arrive
                if kind == "pass" and e.get("outcome") == "complete" and e.get("receiver"):
                    add(e["receiver"], arrive, end, P_LINK, release=t - ANTICIPATION_S)
                    if nxt is not None and nxt.get("player") == e["receiver"] and nxt["type"] not in DEFENSIVE_ACTIONS:
                        tl.holders.append((arrive, float(nxt["t_s"]), e["receiver"]))
                if kind == "shot" and e.get("outcome") == "saved":
                    keeper = next((n for n in self.on_pitch(self.roster.opponent(team), t)
                                   if self.roster.players[n].position == "POR"), None)
                    if keeper:
                        add(keeper, arrive, end, P_LINK, release=t - 0.5)
                if kind == "shot" and e.get("outcome") == "goal":
                    last_end_t = arrive
            elif nxt is not None and nxt.get("player") == e["player"] and nxt["type"] not in DEFENSIVE_ACTIONS:
                tl.holders.append((t, float(nxt["t_s"]), e["player"]))
        for name in anchors:
            anchors[name] = self._resolve(sorted(anchors[name], key=lambda a: (a.t, -a.priority)))
        tl.anchors = anchors
        # --- the ball while it is out: it waits off the pitch, then goes to the spot of the restart
        flight = sorted(ball)
        keys = list(flight)
        for d in tl.dead:
            if d.end - d.start < 3.0:
                continue
            if d.out_at == "net":  # the ball stays in the goal, then goes back to the centre spot
                before = [k for k in flight if k[0] <= d.start]
                if before:
                    keys.append((d.start + 3.0, before[-1][1], before[-1][2]))
                keys.append((max(d.start + 4.0, d.end - 6.0), d.spot[0], d.spot[1]))
            elif d.out_at is not None:
                ox, oy = d.out_at
                ox = -1.5 if ox <= 0.0 else (PITCH_LENGTH + 1.5 if ox >= PITCH_LENGTH else ox)
                oy = -1.5 if oy <= 0.0 else (PITCH_WIDTH + 1.5 if oy >= PITCH_WIDTH else oy)
                keys.append((d.start + 1.0, ox, oy))
                keys.append((max(d.start + 1.5, d.end - 3.0), ox, oy))
            else:
                keys.append((max(d.start + 0.5, d.end - 3.0), d.spot[0], d.spot[1]))
        keys.append((0.0, PITCH_LENGTH / 2, PITCH_WIDTH / 2))
        keys.append((float(HALF_LENGTH_S), PITCH_LENGTH / 2, PITCH_WIDTH / 2))
        keys.append((float(MATCH_LENGTH_S), keys[-1][1], keys[-1][2]))
        tl.ball_keys = sorted(set(keys))
        return tl

    @staticmethod
    def _resolve(items: list[Anchor]) -> list[Anchor]:
        """Two anchors closer in time than a player can run between them: keep the stronger one."""
        out: list[Anchor] = []
        for a in items:
            while out:
                b = out[-1]
                dt = a.t - b.t
                need = math.dist((a.x, a.y), (b.x, b.y)) / max(dt, DT)
                if dt < 0.75 and math.dist((a.x, a.y), (b.x, b.y)) < 1.0:
                    if a.priority > b.priority:
                        out.pop()
                        continue
                    a = None
                    break
                if need > V_PLAY * 1.15 and a.priority <= b.priority:
                    a = None
                    break
                if need > V_PLAY * 1.15:
                    out.pop()
                    continue
                break
            if a is not None:
                out.append(a)
        return out

    # ------------------------------------------------------------ state at t
    def possession_at(self, t: float) -> str:
        times = [p[0] for p in self.timeline.possession]
        i = bisect.bisect_right(times, t) - 1
        return self.timeline.possession[max(i, 0)][1]

    def dead_at(self, t: float) -> DeadBall | None:
        for d in self._dead_sorted:
            if d.start <= t <= d.end:
                return d
            if d.start > t:
                break
        return None

    def ball_at(self, t: float) -> tuple[float, float]:
        keys = self.timeline.ball_keys
        i = bisect.bisect_right(self._ball_times, t) - 1
        if i < 0:
            return keys[0][1], keys[0][2]
        if i >= len(keys) - 1:
            return keys[-1][1], keys[-1][2]
        t0, x0, y0 = keys[i]
        t1, x1, y1 = keys[i + 1]
        w = 0.0 if t1 <= t0 else (t - t0) / (t1 - t0)
        return x0 + (x1 - x0) * w, y0 + (y1 - y0) * w

    def press_of(self, team: str, t: float) -> float:
        press = DEFAULT_STYLE["press"]
        for p in self.phases:
            if p.get("team") == team and p["from"] <= t < p["to"] and "press" in p:
                press = float(p["press"])
        return press

    # ------------------------------------------------------------ shape
    def shape(self, team: str, name: str, t: float, ball: tuple[float, float], dead: DeadBall | None) -> tuple[float, float]:
        position = self.roster.players[name].position
        lane_p, lane_y = self.lanes[name]
        home = self.home
        bp = prog_of(ball[0], team, home)
        by = ball[1]
        if dead is not None and team != dead.team and position != "POR" and dead.kind in ("free_kick", "throw_in"):
            return self._keep_distance(team, name, t, dead)
        if dead is not None and dead.kind in SET_SHAPES:
            spot_p = prog_of(dead.spot[0], team, home)
            got = SET_SHAPES[dead.kind](self, team, name, position, lane_p, lane_y, dead, spot_p)
            if got is not None:
                p, y = got
                return clamp_pitch(x_of(p, team, home), y, 1.0)
            ball = dead.spot
            bp, by = prog_of(ball[0], team, home), ball[1]
        if position == "POR":
            p = clip(4.0 + 0.12 * max(bp - 20.0, 0.0), 2.0, 18.0)
            y = clip(34.0 + 0.2 * (by - 34.0), 29.0, 39.0)
            return clamp_pitch(x_of(p, team, home), y, 0.5)
        with_ball = self.possession_at(t) == team
        if with_ball:
            p = lane_p + 0.55 * (bp - 52.5) + 4.0
            y = 34.0 + (lane_y - 34.0) * 1.08 + 0.2 * (by - 34.0)
            # onside: nobody waits beyond the rival's back line, unless the ball is already there
            rival = self.roster.opponent(team)
            rival_line = 40.0 + 0.55 * ((PITCH_LENGTH - bp) - 52.5) + \
                (self.press_of(rival, t) - DEFAULT_STYLE["press"]) * 22.0 + (24.0 - 46.0) * 0.78
            p = min(p, max(PITCH_LENGTH - max(rival_line, 6.0), bp) + 0.5, 98.0)
        else:
            height = (self.press_of(team, t) - DEFAULT_STYLE["press"]) * 22.0
            centre = 40.0 + 0.55 * (bp - 52.5) + height
            p = centre + (lane_p - 46.0) * 0.78
            y = 34.0 + (lane_y - 34.0) * 0.76 + 0.36 * (by - 34.0)
            if position in ("DFC", "LD", "LI"):
                p = min(p, max(bp - 3.0, 12.0))  # the back line stays goal side of the ball
        p = clip(p, 3.0, 101.0)
        sx, sy = self._sway(name, t)
        return clamp_pitch(x_of(p, team, home) + sx, y + sy, 1.0)

    def _sway(self, name: str, t: float) -> tuple[float, float]:
        """A slow, deterministic drift around the spot, so nobody stands still like a statue."""
        seed = sum(ord(c) * (i + 1) for i, c in enumerate(name))
        phase = (seed % 628) / 100.0
        period = 9.0 + seed % 5
        return (SWAY_M * math.sin(2 * math.pi * t / period + phase),
                SWAY_M * 0.8 * math.cos(2 * math.pi * t / (period * 1.37) + phase * 1.7))

    def _keep_distance(self, team: str, name: str, t: float, dead: DeadBall) -> tuple[float, float]:
        """Rivals of a free kick stand 9.15 m away, three of them in a wall when it is close to goal.
        At a throw-in they only step 2 m away."""
        gap = FREE_KICK_GAP_M + 0.35 if dead.kind == "free_kick" else 2.0
        wall = self._wall(team, dead) if dead.kind == "free_kick" else []
        if name in wall:
            gx = x_of(0.0, team, self.home)
            dx, dy = gx - dead.spot[0], PITCH_WIDTH / 2 - dead.spot[1]
            d = math.hypot(dx, dy) or 1.0
            ux, uy = dx / d, dy / d
            k = wall.index(name) - (len(wall) - 1) / 2
            return clamp_pitch(dead.spot[0] + ux * FREE_KICK_GAP_M - uy * k * 0.8,
                               dead.spot[1] + uy * FREE_KICK_GAP_M + ux * k * 0.8)
        x, y = self.shape(team, name, t, dead.spot, None)
        dx, dy = x - dead.spot[0], y - dead.spot[1]
        d = math.hypot(dx, dy)
        if d < gap:
            if d < 1e-6:
                dx, dy, d = (-1.0 if team == self.home else 1.0), 0.0, 1.0
            x, y = dead.spot[0] + dx / d * gap, dead.spot[1] + dy / d * gap
        return clamp_pitch(x, y, 1.0)

    def _wall(self, team: str, dead: DeadBall) -> list[str]:
        key = (dead.end, team)
        if key not in self._walls:
            names = []
            if prog_of(dead.spot[0], team, self.home) <= 32.0 and abs(dead.spot[1] - 34.0) <= 22.0:
                outfield = [n for n in self.on_pitch(team, dead.end) if self.roster.players[n].position not in ("POR", "DFC")]
                gx = x_of(0.0, team, self.home)
                wx, wy = (dead.spot[0] + gx) / 2, (dead.spot[1] + 34.0) / 2
                lanes = {n: (x_of(self.lanes[n][0], team, self.home), self.lanes[n][1]) for n in outfield}
                names = sorted(outfield, key=lambda n: math.dist(lanes[n], (wx, wy)))[:3]
                names.sort(key=lambda n: lanes[n][1])
            self._walls[key] = names
        return self._walls[key]

    # ------------------------------------------------------------ simulate
    def build(self) -> dict:
        tl = self.timeline
        self._walls = {}
        self._dead_sorted = sorted(tl.dead, key=lambda d: d.start)
        self._ball_times = [k[0] for k in tl.ball_keys]
        anchor_times = {n: [a.t for a in a_list] for n, a_list in tl.anchors.items()}
        holder_list = sorted(tl.holders)
        self._event_times = {float(e["t_s"]) for e in self.events if e.get("start") is not None and e.get("team")}
        n_frames = int(MATCH_LENGTH_S * HZ) + 1
        pos: dict[str, tuple[float, float]] = {}
        frames = []
        for k in range(n_frames):
            t = k * DT
            restart = t in (0.0, float(HALF_LENGTH_S))
            dead = self.dead_at(t)
            ball = self.ball_at(t)
            teams = {team: self.on_pitch(team, t) for team in (self.home, self.away)}
            if restart:  # kick-off: everybody already in place (the teams come out of the tunnel)
                for team, names in teams.items():
                    for name in names:
                        pos[name] = self.shape(team, name, t, ball, dead)
                    for name in names:
                        a = self._anchor_now(name, t, anchor_times)
                        if a is not None:
                            pos[name] = (a.x, a.y)
            vmax = V_DEAD if dead is not None else V_PLAY
            engaged: set[str] = set()
            holder_now = None if dead is not None or restart else self._holder_at(t, holder_list)
            roles = {} if holder_now is None or holder_now not in pos else \
                self._roles(t, teams, pos, holder_now, anchor_times)
            for team, names in teams.items():
                for name in names:
                    if name not in pos:  # a substitute takes the place of the player he replaces
                        out = next((c["player_out"] for c in self.changes if c["player_in"] == name), None)
                        pos[name] = pos.get(out) or self.shape(team, name, t, ball, dead)
                    if restart:
                        continue
                    cur = pos[name]
                    target_anchor = self._next_anchor(name, t, anchor_times)
                    if dead is not None and dead.taker == name and dead.end - t <= max(dead.end - dead.start, 0):
                        target_anchor = Anchor(dead.end, dead.spot[0], dead.spot[1], P_ACTOR)
                    if target_anchor is not None:
                        engaged.add(name)
                        remaining = max(target_anchor.t - t, 0.0)
                        dx, dy = target_anchor.x - cur[0], target_anchor.y - cur[1]
                        dist = math.hypot(dx, dy)
                        if remaining <= 1e-6:
                            step = dist
                            cap = max(vmax, V_PLAY) * DT * 1.3
                        else:
                            frames_left = remaining / DT
                            step = dist / max(frames_left, 1.0)
                            cap = (V_PLAY * 1.12 if target_anchor.priority >= P_LINK else V_PLAY) * DT
                        step = min(step, cap) if remaining > 1e-6 else min(step, cap)
                        if dist > 1e-9:
                            pos[name] = (cur[0] + dx / dist * step, cur[1] + dy / dist * step)
                        continue
                    if name in roles:  # pressing, covering, tracking a run or offering a pass
                        tx, ty, lag, speed = roles[name]
                    else:
                        tx, ty = self.shape(team, name, t, ball, dead)
                        lag, speed = SHAPE_LAG_S, (V_CRUISE if dead is None else vmax)
                    if self._holding(name, t, holder_list):
                        engaged.add(name)
                    dx, dy = tx - cur[0], ty - cur[1]
                    dist = math.hypot(dx, dy)
                    want = dist * DT / lag
                    step = min(want, speed * DT)
                    if dist > 1e-9:
                        pos[name] = (cur[0] + dx / dist * step, cur[1] + dy / dist * step)
            on = teams[self.home] + teams[self.away]
            self._separate(on, pos, engaged, dead)
            if dead is not None and dead.kind in RIVAL_GAP and t < dead.end:
                gap = RIVAL_GAP[dead.kind]
                for name in teams[self.roster.opponent(dead.team)]:
                    x, y = pos[name]
                    dx, dy = x - dead.spot[0], y - dead.spot[1]
                    d = math.hypot(dx, dy)
                    if d < gap and self.roster.players[name].position != "POR":
                        if d < 1e-6:
                            dx, dy, d = 0.0, 1.0, 1.0
                        pos[name] = clamp_pitch(dead.spot[0] + dx / d * gap, dead.spot[1] + dy / d * gap)
            holder = None if dead is not None or t in self._event_times else self._holder_at(t, holder_list)
            if holder is not None and holder in pos:  # at the second of an action the ball is where it happened
                hx, hy = pos[holder]
                ahead = BALL_AT_FOOT_M if self.roster.players[holder].team == self.home else -BALL_AT_FOOT_M
                ball = clamp_pitch(hx + ahead, hy, 0.2)
            frames.append((t, ball, [pos[n] for n in teams[self.home]], [pos[n] for n in teams[self.away]]))
        return self._output(frames)

    def _roles(self, t: float, teams: dict, pos: dict, holder: str, anchor_times) -> dict:
        """Who presses the carrier, who covers, who tracks a run and who offers a pass, this frame.

        Only players with no event of their own coming up take a role: the events always win."""
        attack = self.roster.players[holder].team
        defend = self.roster.opponent(attack)
        bx, by = pos[holder]
        free = lambda name: self.roster.players[name].position != "POR" and not self._busy(name, t, anchor_times)
        roles: dict[str, tuple[float, float, float, float]] = {}
        # the rival's own goal and the direction to it from the ball
        gx = x_of(0.0, defend, self.home)
        ux, uy = gx - bx, PITCH_WIDTH / 2 - by
        norm = math.hypot(ux, uy) or 1.0
        ux, uy = ux / norm, uy / norm
        defenders = sorted((n for n in teams[defend] if free(n)), key=lambda n: math.dist(pos[n], (bx, by)))
        press = clip((self.press_of(defend, t) - 0.2) / 0.5, 0.0, 1.0)
        gap = PRESS_GAP_M[1] - (PRESS_GAP_M[1] - PRESS_GAP_M[0]) * press
        if defenders:
            roles[defenders[0]] = (*clamp_pitch(bx + ux * gap, by + uy * gap, 1.0), 1.0, 6.5)
        if len(defenders) > 1:
            roles[defenders[1]] = (*clamp_pitch(bx + ux * COVER_GAP_M, by + uy * COVER_GAP_M, 1.0), 1.8, 5.0)
        # a run nobody was told to follow: the nearest free defender tracks it, goal side
        for t0, t1, runner, team, marked in self.timeline.runs:
            if t0 <= t <= t1 and team == attack and not marked and runner in pos:
                rx, ry = pos[runner]
                left = [n for n in defenders[2:] if n not in roles]
                if left:
                    marker = min(left, key=lambda n: math.dist(pos[n], (rx, ry)))
                    vx, vy = gx - rx, PITCH_WIDTH / 2 - ry
                    d = math.hypot(vx, vy) or 1.0
                    roles[marker] = (*clamp_pitch(rx + vx / d * MARK_GAP_M, ry + vy / d * MARK_GAP_M, 1.0), 0.5, V_PLAY)
        # two team-mates offer the pass: one behind and wide, one ahead on the other side
        forward = 1.0 if attack == self.home else -1.0
        wide = 1.0 if by < PITCH_WIDTH / 2 else -1.0  # towards the middle of the pitch
        spots = [(bx - forward * SUPPORT_M[0], by + wide * SUPPORT_M[1]),
                 (bx + forward * SUPPORT_M[0], by - wide * SUPPORT_M[1] * 0.8)]
        mates = [n for n in teams[attack] if n != holder and free(n)]
        for sx, sy in spots:
            sx, sy = clamp_pitch(sx, sy, 2.0)
            if mates:
                mate = min(mates, key=lambda n: math.dist(pos[n], (sx, sy)))
                mates.remove(mate)
                roles[mate] = (sx, sy, 2.0, 4.5)
        return roles

    def _busy(self, name: str, t: float, anchor_times, horizon: float = 4.0) -> bool:
        """He has an action of his own within ``horizon`` seconds (or one released already): no role for him."""
        if self._next_anchor(name, t, anchor_times) is not None:
            return True
        lst = self.timeline.anchors.get(name, [])
        i = bisect.bisect_left(anchor_times[name], t - 1e-9)
        return i < len(lst) and lst[i].t - t <= horizon

    def _anchor_now(self, name: str, t: float, anchor_times) -> Anchor | None:
        lst = self.timeline.anchors.get(name, [])
        i = bisect.bisect_left(anchor_times[name], t - 1e-9)
        if i < len(lst) and abs(lst[i].t - t) < DT / 2:
            return lst[i]
        return None

    def _next_anchor(self, name: str, t: float, anchor_times) -> Anchor | None:
        lst = self.timeline.anchors.get(name, [])
        i = bisect.bisect_left(anchor_times[name], t - 1e-9)
        if i < len(lst):
            a = lst[i]
            if (a.release is not None and t >= a.release) or (a.release is None and a.t - t <= a.window):
                return a
        return None

    @staticmethod
    def _holder_at(t: float, holders) -> str | None:
        """Who carries the ball at ``t``: from the moment it reaches him to his next action, both excluded."""
        i = bisect.bisect_right(holders, (t, float("inf"), "")) - 1
        while i >= 0 and holders[i][0] <= t:
            start, end, name = holders[i]
            if start < t < end:
                return name
            if t - start > 60:
                break
            i -= 1
        return None

    @staticmethod
    def _holding(name: str, t: float, holders) -> bool:
        i = bisect.bisect_right(holders, (t, float("inf"), "")) - 1
        while i >= 0 and holders[i][0] <= t:
            if holders[i][2] == name and holders[i][1] >= t:
                return True
            if t - holders[i][0] > 60:
                break
            i -= 1
        return False

    def _separate(self, names: list[str], pos: dict, engaged: set[str], dead: DeadBall | None) -> None:
        """Rivals keep 1.5 m apart (marking close is normal). Team-mates keep the width of a disc, except
        in a wall or in the box at a corner."""
        crowded = dead is not None and dead.kind in ("corner", "free_kick")
        team_of = {n: self.roster.players[n].team for n in names}
        for _ in range(2):
            for i in range(len(names)):
                a = names[i]
                ax, ay = pos[a]
                for j in range(i + 1, len(names)):
                    b = names[j]
                    bx, by = pos[b]
                    dx, dy = bx - ax, by - ay
                    d = math.hypot(dx, dy)
                    gap = TEAMMATE_GAP_M if team_of[a] == team_of[b] and not crowded else MIN_GAP_M
                    if d >= gap or (a in engaged and b in engaged):
                        continue
                    if d < 1e-6:
                        dx, dy, d = 0.0, 1.0, 1.0
                    push = (gap - d) / 2
                    ux, uy = dx / d, dy / d
                    if a not in engaged:
                        pos[a] = clamp_pitch(ax - ux * push * (2 if b in engaged else 1), ay - uy * push * (2 if b in engaged else 1))
                        ax, ay = pos[a]
                    if b not in engaged:
                        pos[b] = clamp_pitch(bx + ux * push * (2 if a in engaged else 1), by + uy * push * (2 if a in engaged else 1))

    # ------------------------------------------------------------ output
    def _output(self, frames) -> dict:
        def pt(p):
            return [round(p[0], 1), round(p[1], 1)]

        def roster_of(team):
            return [{"slot": i, "player": n, "number": self.roster.players[n].number,
                     "position": self.roster.players[n].position} for i, n in enumerate(self.lineups[team])]

        set_pieces = [{"t_s": d.end, "kind": d.kind, "team": "home" if d.team == self.home else "away",
                       "taker": d.taker, "spot": pt(d.spot), "ball_out_from_t_s": round(d.start, 1)}
                      for d in sorted(self.timeline.dead, key=lambda d: d.end)]
        changes = [dict(c, number=self.roster.players[c["player_in"]].number,
                        position=self.roster.players[c["player_in"]].position) for c in self.changes]
        return {
            "match_id": self.match_id,
            "illustrative": True,
            "hz": HZ,
            "coordinates": "metres on 105 x 68, origin bottom left, home attacks x = 105 in both halves, as the events",
            "periods": [
                {"period": 1, "from_t_s": 0, "to_t_s": HALF_LENGTH_S, "home_attacks": "right", "rotate_180": False},
                {"period": 2, "from_t_s": HALF_LENGTH_S, "to_t_s": MATCH_LENGTH_S, "home_attacks": "left", "rotate_180": True},
            ],
            "teams": {"home": {"name": self.home, "players": roster_of(self.home)},
                      "away": {"name": self.away, "players": roster_of(self.away)}},
            "lineup_changes": changes,
            "set_pieces": set_pieces,
            "frames": [{"t": round(t, 1), "b": pt(b), "h": [pt(p) for p in h], "a": [pt(p) for p in a]}
                       for t, b, h, a in frames],
        }


# ---------------------------------------------------------------- set piece shapes
# Each returns (progress from the team's own goal, y) or None to fall back on the open-play shape
# with the ball at the spot. ``spot_p`` is the spot's progress for this team.
def _side(dead: DeadBall) -> float:
    return 1.0 if dead.spot[1] >= PITCH_WIDTH / 2 else -1.0


def _kickoff(model, team, name, position, lane_p, lane_y, dead, spot_p):
    if position == "POR":
        return 4.0, 34.0
    p = min(lane_p * 0.62 + 4.0, 50.5)
    if dead.team != team and abs(lane_y - 34.0) < 12:
        p = min(p, 52.5 - FREE_KICK_GAP_M - 0.5)
    return p, lane_y


CORNER_ATTACK = {"DFC": [(94.5, -4.0), (96.0, 5.0)], "DC": [(98.5, 1.0)], "MC": [(90.0, -7.0), (60.0, 0.0)],
                 "ED": [(95.5, 9.0)], "EI": [(95.5, 9.0)], "MCD": [(68.0, 0.0)], "LD": [(55.0, -14.0)],
                 "LI": [(55.0, 14.0)], "POR": [(20.0, 0.0)]}
CORNER_DEFEND = {"POR": [(0.8, 1.5)], "DFC": [(5.5, -3.0), (6.0, 4.0)], "LD": [(3.0, -6.0)], "LI": [(3.0, 6.0)],
                 "MCD": [(9.0, 0.0)], "MC": [(11.0, -6.0), (12.0, 6.0)], "ED": [(14.0, -12.0)], "EI": [(14.0, 12.0)],
                 "DC": [(28.0, 0.0)]}


def _role_index(model, team, name, position, t) -> int:
    same = [n for n in model.on_pitch(team, t) if model.roster.players[n].position == position]
    return same.index(name) if name in same else 0


def _corner(model, team, name, position, lane_p, lane_y, dead, spot_p):
    if name == dead.taker:
        return None
    side = _side(dead)
    table = CORNER_ATTACK if team == dead.team else CORNER_DEFEND
    spots = table.get(position)
    if not spots:
        return None
    p, dy = spots[min(_role_index(model, team, name, position, dead.end), len(spots) - 1)]
    if team != dead.team and position in ("LD", "LI", "ED", "EI"):
        dy = abs(dy) * (1 if (lane_y > 34) else -1)
        return p, 34.0 + dy
    return p, 34.0 + side * dy


GOAL_KICK_DEPTH = {"POR": 5.0, "DFC": 13.0, "LD": 24.0, "LI": 24.0, "MCD": 30.0, "MC": 42.0, "ED": 55.0, "EI": 55.0,
                   "DC": 62.0}


def _goal_kick(model, team, name, position, lane_p, lane_y, dead, spot_p):
    if team == dead.team:  # the team restarting spreads out: centre-backs wide at the edge of the box
        if name == dead.taker:
            return None
        y = 34.0 + (lane_y - 34.0) * (2.2 if position == "DFC" else 1.12)
        return GOAL_KICK_DEPTH.get(position, lane_p), clip(y, 2.0, 66.0)
    if position == "POR":
        return 12.0, 34.0
    return min(lane_p * 0.9 + 14.0, PITCH_LENGTH - 17.5), lane_y  # the rival waits outside the box


def _keeper(model, team, name, position, lane_p, lane_y, dead, spot_p):
    if team == dead.team:
        if position == "POR":
            return None
        return min(lane_p + 2.0, 60.0), clip(34.0 + (lane_y - 34.0) * 1.15, 2.0, 66.0)
    if position == "POR":
        return None
    return min(lane_p * 0.7 + 18.0, PITCH_LENGTH - 20.0), lane_y


def _free_kick(model, team, name, position, lane_p, lane_y, dead, spot_p):
    return None  # the open-play shape with the ball at the spot; the gap and the wall come after


def _throw_in(model, team, name, position, lane_p, lane_y, dead, spot_p):
    return None


SET_SHAPES = {"kickoff": _kickoff, "corner": _corner, "goal_kick": _goal_kick, "keeper": _keeper,
              "free_kick": _free_kick, "throw_in": _throw_in}


def build_positions(events: list[dict], roster: Roster, script: str | dict | None = None) -> dict:
    """Positions file of ``contracts/positions.schema.json`` for one match."""
    return PositionModel(events, roster, script).build()
