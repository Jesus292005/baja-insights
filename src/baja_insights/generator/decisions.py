"""Free matches where every decision comes from the play, not from a script.

``generate_match(..., script=None)`` uses this generator. The demo match ``m001`` keeps the scripted
``MatchGenerator`` exactly as it was, event for event, so this module can change without touching it.

What changes against the scripted generator
-------------------------------------------
* **Who acts is who is there.** The generator knows where each block stands at every moment, with the
  same shape the positions model draws: the team slides with the ball, opens up with it, closes down
  without it and its back line stays goal side. The one who presses, wins a loose ball, disputes a duel
  or receives a pass is one of the players nearest to that spot; his card only breaks the tie.
* **A loose ball is picked up when the nearest rival can reach it**, not after a fixed pause.
* **Profiles come from the cards** in ``teams.json`` (ritmo, disparo, vision, regate, defensa, fisico,
  sin_balon): a sharp shooter shoots more, a good passer finds the free team-mate, a strong defender
  wins more tackles. Every multiplier stays within about 0.85 to 1.2.
* **Shooting depends on the chance.** Close to goal and free, a player almost always shoots; from far
  out, rarely. Inside the box, a player who cannot shoot looks for the team-mate in a better spot.
* **Penalties.** Fouls inside the box are rare, as in the Premier League, and each one is a penalty: a
  shot from the spot with ``set_piece: "penalty"`` and its xG.
* **The score changes the rhythm, never the finishing.** ``tactics.json`` says how each team plays and
  how it reacts: the team ahead slows down and sits back, the team behind speeds up and presses but
  meets a crowded box. A shot always goes in with the probability of its xG.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from ..contract import PITCH_LENGTH, PITCH_WIDTH, clip, distance
from ..roster import Roster
from .simulate import (
    DEFAULT_STYLE, GEN, RESTART_PAUSE_S, ROLE_FACTOR, SET_PIECES, MatchGenerator, Resume, travel_time,
)
from .xg import expected_goals

TACTICS_PATH = Path(__file__).resolve().parent / "tactics.json"

DEC = {
    "act_sigma": 6.0,         # metres: how strongly the nearest player is preferred for a defensive action
    "receive_sigma": 8.0,     # ... and for receiving a pass
    "near_band": 10.0,        # only players this much farther than the nearest are considered
    "loose_speed": 6.0,       # m/s of the player who goes for a loose ball
    "shot_min_prog": 72.0,    # metres from own goal where a player starts to consider shooting
    "shot_x0": 0.27,          # xG at which a player with an average shooting card shoots half the time
    "shot_s": 0.045,          # how sharp that choice is
    "square_margin": 0.05,    # a team-mate needs this much more xG to be worth the pass inside the box
    "square_prob": 0.7,       # ... and the pass is tried this often, times the passer's vision
    "foul_box": 0.18,         # fouls inside the box are this much rarer than elsewhere
    "penalty_xg": 0.76,       # Premier League penalties go in about three times out of four
    "penalty_pause": (50, 80),
    "blocked_crowded": 0.45,  # share of missed shots that are blocked against a crowded box (else 0.3)
    "final_third": 75.0,      # from here the defence is compact near its goal ...
    "close_down": 0.35,       # ... and closes the carrier down at least this often (more in the box)
    "close_down_box": 0.8,
    "deepest_carry": 90.0,    # nobody runs with the ball deep into the box: defenders are there
    "free_in_box": 0.35,
    "contain": 0.6,
    "press_speed": 6.5,       # m/s of the presser closing the carrier down
    "memory_s": 4.0,          # a player who acted this recently is still where he acted
    "release": 0.5,           # a pressed carrier lets the ball go before the presser arrives this often (average card)
    "release_s": (0.3, 0.8),  # ... in this many seconds, one or two touches
    "one_touch": 0.18,        # unpressed, he still plays it first time this often
    "hold_risk": 1.6,         # the one who waits for the presser loses it this much more often
    "held_pass_hard": 0.45,   # a pass with the presser on him is much harder (about 65-70% completed)
    "quick_pass_hard": 0.08,  # ... a pass released before he arrives, barely
    "dribble": 0.25,          # the one who holds it takes the presser on this often, times his dribbling
    "look_s": (0.9, 2.8),     # seconds to look up and pick the pass after a carry, before tempo
    "first_time_xg": 0.9,     # a first-time shot is a little worse than a settled one
    "first_time_x0": 0.23,    # xG at which a player with an average shooting card shoots first time half the time
    "marked_on_arrival": 0.55,  # inside the box the defender is already on him when the ball arrives
    "counter_steps": 3,       # actions on the break after winning the ball in the own half
    "counter_tempo": 1.6,
    "counter_direct": 0.3,
    "counter_press": 0.5,     # the rival, caught upfield, presses less
    "counter_runs": 3.0,      # and team-mates break forward
    "foul_rate": 1.25,        # fouls happen on the actions where he keeps the ball, not on the quick ones
    "accuracy": 0.18,         # base share of shots on target (plus half the xG): about a third on target
    "decoy_pass": 0.6,
    "run_rate": 0.05,         # chance per action in the last 40 m that a team-mate makes a run in behind
    "run_drags": 0.45,        # ... and that the run drags a defender with him        # a run that drags a defender and does not get the ball: the pass goes into the space
    "out_near_goal": 0.7,     # a misplaced ball towards the box goes out this often (else 50%)
    "deepest_run": 96.0,      # a run in behind ends at the edge of the goal area at most ...
    "deepest_pass": 99.0,     # ... and so does a pass aimed at the box
    "cross_shot": 0.25,       # a completed cross ends in a header or a volley; most are cleared or controlled           # tackles tried near the own goal, against elsewhere
    "long_shot": 0.025,        # chance per action of a shot from outside the box with room, average card
    "attack_line_max": 94.0,  # attackers wait at the penalty spot at most: the goal area is the keeper's
    "cross_hard": 0.9,        # a cross into a crowded box is completed less often (about a quarter)
    "final_third_hard": 0.45,  # passing against a compact defence is harder (about 70% completed)      # a team-mate in the box is unmarked this often
}
BOX_DEPTH_M = 16.5
BOX_HALF_WIDTH_M = 20.16
PENALTY_SPOT_PROG = PITCH_LENGTH - 11.0


def in_box(prog: float, y: float) -> bool:
    return prog >= PITCH_LENGTH - BOX_DEPTH_M and abs(y - PITCH_WIDTH / 2) <= BOX_HALF_WIDTH_M


def skill(card: dict, key: str) -> float:
    """A card attribute (0-100, 50 is average) as a multiplier around 1."""
    return 0.75 + float(card.get(key, 50)) / 200.0


def load_tactics(tactics: dict | str | Path | None = None) -> dict:
    if isinstance(tactics, dict):
        return tactics
    return json.loads(Path(tactics or TACTICS_PATH).read_text(encoding="utf-8"))


class DecisionGenerator(MatchGenerator):
    def __init__(self, roster: Roster, seed: int, match_id: str | None = None,
                 tactics: dict | str | Path | None = None):
        super().__init__(roster, seed=seed, script=None, match_id=match_id)
        self.tactics = load_tactics(tactics)
        self.ball_xy = (PITCH_LENGTH / 2, PITCH_WIDTH / 2)
        self.last_goal_t = -1e9
        self.last_seen: dict[str, tuple[float, float, float]] = {}  # name -> (t, x, y) of his last action
        # good and bad days: each team plays a little better or worse than usual in this match
        sd = float(self.tactics.get("game_state", {}).get("day_form_sd", 0.0))
        self.day = {team: clip(self.rng.gauss(1.0, sd), 1.0 - 2 * sd, 1.0 + 2 * sd) if sd else 1.0
                    for team in (self.home, self.away)}

    # ============================================================ profiles
    def _card(self, name: str | None) -> dict:
        player = self.roster.players.get(name) if name else None
        return player.card if player else {}

    def _skill(self, name: str | None, key: str) -> float:
        return skill(self._card(name), key)

    def _form(self, name: str | None, key: str) -> float:
        """The scripted generator's form, now read from the card."""
        if name is None:
            return 1.0
        card = self._card(name)
        if key == "duel_win":
            best = max(card.get("regate", 50), card.get("defensa", 50))
            return 0.75 + (best + card.get("fisico", 50)) / 400.0
        attribute = {"recover": "defensa", "press": "fisico", "receive": "sin_balon", "pass_lines": "vision"}.get(key)
        return skill(card, attribute) if attribute else 1.0

    # ============================================================ tactics
    def _margin(self, team: str) -> int:
        side = "home" if team == self.home else "away"
        return self.scoreline[side] - self.scoreline["away" if side == "home" else "home"]

    def _style(self, team: str) -> dict:
        style = dict(DEFAULT_STYLE)
        style.update({k: v for k, v in self.tactics.get("teams", {}).get(team, {}).items() if k in DEFAULT_STYLE})
        gs = self.tactics.get("game_state", {})
        day = self.day.get(team, 1.0)
        style["pass_acc"] += 0.25 * (day - 1.0)
        margin = self._margin(team)
        if margin:
            change = gs.get("leading" if margin > 0 else "trailing", {})
            weight = min(abs(margin), 2)
            style["tempo"] *= change.get("tempo", 1.0) ** weight
            style["press"] += change.get("press", 0.0) * weight
            style["directness"] += change.get("directness", 0.0) * weight
        if self.t - self.last_goal_t < gs.get("calm_after_goal_s", 0):
            style["tempo"] *= gs.get("calm_tempo", 1.0)
        if self.t >= gs.get("late_from_s", 1e9):
            style["press"] *= gs.get("late_press", 1.0)
        style["press"] = clip(style["press"], 0.05, 0.9)
        style["directness"] = clip(style["directness"], 0.1, 0.9)
        return style

    def _aggression(self, team: str) -> float:
        return float(self.tactics.get("teams", {}).get(team, {}).get("aggression", 1.0))

    def _crowded(self, defending: str) -> bool:
        """The team ahead packs its box: a shot against it is more often taken under pressure."""
        lead = self._margin(defending)
        share = self.tactics.get("game_state", {}).get("crowded_box", 0.0)
        return lead > 0 and self.rng.random() < share * min(lead, 2)

    # ============================================================ where everyone is
    def _spot(self, name: str) -> tuple[float, float]:
        """Where ``name`` stands now, with the ball at ``ball_xy``: the shape the positions model draws."""
        player = self.roster.players[name]
        team = player.team
        lane_p, lane_y = self.lanes[name]
        bx, by = self.ball_xy
        bp = self._prog(bx, team)
        if player.position == "POR":
            p = clip(4.0 + 0.12 * max(bp - 20.0, 0.0), 2.0, 18.0)
            return self._to_x(p, team), clip(34.0 + 0.2 * (by - 34.0), 29.0, 39.0)
        owner = self.current[0] if self.current else None
        if owner == team:
            p = lane_p + 0.55 * (bp - 52.5) + 4.0
            y = 34.0 + (lane_y - 34.0) * 1.08 + 0.2 * (by - 34.0)
            rival = self.roster.opponent(team)
            rival_line = 40.0 + 0.55 * ((PITCH_LENGTH - bp) - 52.5) + \
                (self._style(rival)["press"] - DEFAULT_STYLE["press"]) * 22.0 + (24.0 - 46.0) * 0.78
            p = min(p, max(PITCH_LENGTH - max(rival_line, 6.0), bp) + 0.5, DEC["attack_line_max"])
        else:
            height = (self._style(team)["press"] - DEFAULT_STYLE["press"]) * 22.0
            p = 40.0 + 0.55 * (bp - 52.5) + height + (lane_p - 46.0) * 0.78
            y = 34.0 + (lane_y - 34.0) * 0.76 + 0.36 * (by - 34.0)
            if player.position in ("DFC", "LD", "LI"):
                p = min(p, max(bp - 3.0, 12.0))
        return self._to_x(clip(p, 3.0, 101.0), team), clip(y, 1.0, PITCH_WIDTH - 1.0)

    def _where(self, name: str) -> tuple[float, float]:
        """Where he really is: the point of his last action if it was a moment ago, else his spot in the shape."""
        seen = self.last_seen.get(name)
        if seen is not None and self.t - seen[0] < DEC["memory_s"]:
            return seen[1], seen[2]
        return self._spot(name)

    def _append(self, e: dict) -> None:
        super()._append(e)
        t = e["t_s"]
        if e.get("player") and e.get("start") is not None:
            self.last_seen[e["player"]] = (t, e["start"][0], e["start"][1])
        if e["type"] == "off_ball_run" and e.get("end") is not None:
            self.last_seen[e["player"]] = (t + 2.0, e["end"][0], e["end"][1])
            if e.get("dragged_defender") and e.get("dragged_defender_end"):
                self.last_seen[e["dragged_defender"]] = (t + 2.0, *e["dragged_defender_end"])
        if e["type"] == "pass" and e.get("receiver") and e.get("outcome") == "complete":
            self.last_seen[e["receiver"]] = (t + 1.0, e["end"][0], e["end"][1])

    def _zone_xy(self, name: str) -> tuple[float, float]:
        return self._spot(name)

    def _pick(self, team: str, x: float, y: float, weight_key: str | None = None,
              positions: tuple[str, ...] | None = None, exclude: tuple[str, ...] = (),
              exclude_names: tuple[str | None, ...] = ()) -> str | None:
        """One of the players nearest to (x, y) right now; the card and the role only break the tie."""
        roles = ROLE_FACTOR.get(weight_key or "", {})
        candidates = []
        for name in sorted(self.active[team]):
            player = self.roster.players[name]
            if positions and player.position not in positions:
                continue
            if player.position in exclude or name in exclude_names or roles.get(player.position, 1.0) <= 0.0:
                continue
            sx, sy = self._where(name)
            candidates.append((name, math.hypot(sx - x, sy - y), player.position))
        if not candidates:
            return None
        nearest = min(d for _, d, _ in candidates)
        sigma = DEC["receive_sigma"] if weight_key == "receive" else DEC["act_sigma"]
        names, weights = [], []
        for name, d, position in candidates:
            if d > nearest + DEC["near_band"]:
                continue
            w = math.exp(-((d - nearest) / sigma) ** 2)
            if weight_key:
                w *= self._form(name, weight_key) * math.sqrt(roles.get(position, 1.0))
            names.append(name)
            weights.append(w + 1e-9)
        return self.rng.choices(names, weights=weights, k=1)[0]

    # ============================================================ possession
    def _possession(self, r: Resume, limit: float) -> Resume | None:
        team, opp = r.team, self.roster.opponent(r.team)
        pid = r.pid or self._new_pid()
        self.current = (team, pid)
        x, y = r.x, r.y
        if r.kind == "kickoff":
            x, y = PITCH_LENGTH / 2, PITCH_WIDTH / 2
        elif r.kind == "keeper":
            x, y = self._to_x(6.0, team), PITCH_WIDTH / 2
        elif r.kind == "goal_kick":
            x, y = self._to_x(5.5, team), PITCH_WIDTH / 2 + self.rng.uniform(-7.0, 7.0)
        self.ball_xy = (x, y)
        carrier = r.player
        if r.kind == "kickoff":
            carrier = self._pick(team, x, y, positions=("DC",)) or self._pick(team, x, y)
        elif r.kind in ("keeper", "goal_kick"):
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
        arrival = self.t
        run_target = None
        received = False  # the carrier has just received a pass: he may shoot first time
        # a ball won in the own half with the rival pushed up: a few quick, vertical actions
        counter = DEC["counter_steps"] if r.kind in ("recovery", "tackle") and self._prog(x, team) < 60 else 0
        while True:
            if self.t + 3 > limit:
                return self._hold(team, x, y, carrier, pid, set_piece)
            self.ball_xy = (x, y)
            prog = self._prog(x, team)
            box = self._in_box(x, y, team)
            under = quick = beat = False
            pace = dict(style)
            if counter:
                pace["tempo"] *= DEC["counter_tempo"]
                pace["directness"] = clip(pace["directness"] + DEC["counter_direct"], 0.1, 0.95)

            # --- first time: just received in a shooting spot, he shoots before the defender arrives
            if received and not set_piece and prog >= DEC["shot_min_prog"]:
                tight = (box and self.rng.random() < DEC["marked_on_arrival"]) or self._crowded(opp)
                chance = round(max(0.01, expected_goals(prog, y, tight, False) * DEC["first_time_xg"]), 2)
                threshold = DEC["first_time_x0"] / self._skill(carrier, "disparo")
                if self.rng.random() < 1.0 / (1.0 + math.exp(-(chance - threshold) / DEC["shot_s"])):
                    return self._shot(team, carrier, x, y, tight, pid, cross=False, xg=chance)
            received = False

            # --- the nearest rival comes to press, more often when his team presses high; near its own
            # goal the defence is compact and closes the carrier down
            press_prob = opp_style["press"] * (1.25 - prog / PITCH_LENGTH)
            if prog >= DEC["final_third"]:
                press_prob = max(press_prob, DEC["close_down_box"] if box else DEC["close_down"])
            if counter:
                press_prob *= DEC["counter_press"]
            if not set_piece and self.rng.random() < press_prob:
                presser = self._pick(opp, x, y, weight_key="press")
                approach = clip(distance(self._where(presser), [x, y]) / DEC["press_speed"], 0.3, 3.0)
                under = True
                if self.rng.random() < self._release(carrier, prog):
                    # he reads it and lets the ball go just before the presser arrives
                    quick = True
                    self.t += 0.6 * approach
                    self._emit("pressure", opp, presser, [x, y], pid=pid, target=carrier)
                    self.t += self.rng.uniform(*DEC["release_s"]) * 0.5
                else:
                    # he waits for him: the presser gets there, and keeping the ball is a risk
                    self.t += approach
                    self._emit("pressure", opp, presser, [x, y], pid=pid, target=carrier)
                    self.t += self.rng.uniform(0.3, 0.9)
                    position = self.roster.players[presser].position
                    # near his own goal a defender contains rather than dives in: a lost tackle there is a chance
                    attempt = GEN["tackle_attempt"] * ROLE_FACTOR["recover"].get(position, 1.0) * DEC["hold_risk"]
                    if prog >= DEC["final_third"]:
                        attempt *= DEC["contain"]
                    if self.rng.random() < attempt:
                        odds = GEN["tackle_win"] * self._form(presser, "duel_win") / self._form(carrier, "duel_win")
                        won = self.rng.random() < clip(odds, 0.2, 0.85)
                        self._emit("tackle", opp, presser, [x, y], outcome="won" if won else "lost", pid=pid,
                                   opponent=carrier)
                        self.t += self.rng.uniform(1.0, 2.5)
                        if won:
                            return Resume("tackle", opp, x, y, presser)
                        if self.t + 8 < limit and self.rng.random() < GEN["foul_on_lost_tackle"] * self._foul_factor(opp, box):
                            self._emit("foul", opp, presser, [x, y], pid=pid, fouled=carrier)
                            if box:
                                return self._penalty(team, pid, limit)
                            self._free_kick_pause(limit)
                            set_piece = "free_kick"
                            continue
                        beat = True  # he rode the tackle
                    else:
                        win = clip(GEN["press_win"] * self._form(presser, "recover") * opp_style["press"] / 0.3
                                   * DEC["hold_risk"], 0.02, 0.5)
                        if position in ("DC", "ED", "EI"):
                            win *= 0.4
                        if self.rng.random() < win:
                            self.t += self.rng.uniform(0.5, 1.5)
                            return Resume("recovery", opp, x, y, presser)
                        if self.rng.random() < DEC["dribble"] * self._skill(carrier, "regate"):
                            # he takes the presser on
                            fa, fd = self._form(carrier, "duel_win"), self._form(presser, "duel_win")
                            attacker_wins = self.rng.random() < fa / (fa + fd)
                            winner, loser = (carrier, presser) if attacker_wins else (presser, carrier)
                            self._emit("duel", team if attacker_wins else opp, winner, [x, y], outcome="won",
                                       pid=pid, opponent=loser)
                            self.t += self.rng.uniform(0.8, 1.8)
                            if not attacker_wins:
                                return Resume("recovery", opp, x, y, presser)
                            beat = True
                if self.t + 3 > limit:
                    return self._hold(team, x, y, carrier, pid, set_piece)
            elif not set_piece and expected_goals(prog, y, False, False) < DEC["first_time_x0"] \
                    and self.rng.random() < DEC["one_touch"] * self._skill(carrier, "vision"):
                quick = True  # one or two touches and it is gone
                self.t += self.rng.uniform(*DEC["release_s"])

            if not set_piece and not quick:
                # --- he runs with the ball first: far with space, little when pressed, far again if he beat
                # his man or on the break; then he looks up
                x, y = self._carry(team, carrier, x, y, under and not beat, opp_style, arrival,
                                   far=beat or bool(counter))
                self.ball_xy = (x, y)
                prog = self._prog(x, team)
                box = self._in_box(x, y, team)
                self.t += self.rng.uniform(*DEC["look_s"]) / pace["tempo"]

                # --- 1 v 1 duel with the nearest rival
                if not under and self.rng.random() < GEN["duel"]:
                    defender = self._pick(opp, x, y, weight_key="duel", exclude=("POR",))
                    fa, fd = self._form(carrier, "duel_win"), self._form(defender, "duel_win")
                    attacker_wins = self.rng.random() < fa / (fa + fd)
                    winner, loser = (carrier, defender) if attacker_wins else (defender, carrier)
                    self._emit("duel", team if attacker_wins else opp, winner, [x, y], outcome="won", pid=pid,
                               opponent=loser)
                    self.t += self.rng.uniform(1.0, 2.5)
                    if not attacker_wins:
                        return Resume("recovery", opp, x, y, defender)

                # --- shoot when the chance is worth it
                if prog >= DEC["shot_min_prog"]:
                    pressed = (under and not beat) or self._crowded(opp)
                    chance = expected_goals(prog, y, pressed, False)
                    threshold = DEC["shot_x0"] / self._skill(carrier, "disparo")
                    want = 1.0 / (1.0 + math.exp(-(chance - threshold) / DEC["shot_s"]))
                    if not box and not pressed:  # with room outside the box, a good striker of the ball tries it
                        want += DEC["long_shot"] * self._skill(carrier, "disparo") ** 2
                    if self.rng.random() < want:
                        return self._shot(team, carrier, x, y, pressed, pid, cross=False)

                # --- foul suffered: rare inside the box, and then a penalty
                if self.t + 8 < limit and self.rng.random() < GEN["foul"] * DEC["foul_rate"] * self._foul_factor(opp, box):
                    fouler = self._pick(opp, x, y, exclude=("POR",))
                    self._emit("foul", opp, fouler, [x, y], pid=pid, fouled=carrier)
                    if box:
                        return self._penalty(team, pid, limit)
                    self._free_kick_pause(limit)
                    set_piece = "free_kick"
                    continue

                # --- off-ball run by a team-mate near the ball, from where he really is
                runs = DEC["run_rate"] * self._skill(carrier, "vision") * (DEC["counter_runs"] if counter else 1.0)
                if prog > 62 - (25 if counter else 0) and self.rng.random() < runs:
                    runner = self._pick(team, x, y, positions=("ED", "EI", "DC", "MC"), exclude_names=(carrier,))
                    if runner:
                        run_target = self._off_ball_run(team, opp, runner, pid) or run_target

            # --- pass
            passed_at = self.t
            result = self._pass(team, carrier, x, y, under and not beat, pid, pace, set_piece, run_target, quick=quick)
            set_piece = None
            run_target = None
            steps += 1
            counter = max(counter - 1, 0)
            arrival = passed_at + result["travel_s"]
            self.t = max(self.t, arrival) + self.rng.uniform(0.2, 0.5)  # the ball arrives and he controls it
            if result["outcome"] == "complete":
                carrier, x, y = result["receiver"], result["end"][0], result["end"][1]
                received = not result.get("cross")  # a cross is met with a header or a volley, or not at all
                if result.get("cross") and self.rng.random() < DEC["cross_shot"]:
                    if self.t + 2 > limit:
                        return self._hold(team, x, y, carrier, pid, set_piece)
                    self.ball_xy = (x, y)
                    return self._shot(team, carrier, x, y, True, pid, cross=True)
                if steps > 16:
                    if self._prog(x, team) > 70:
                        self.ball_xy = (x, y)
                        return self._shot(team, carrier, x, y, under, pid, cross=False)
                    return self._press_wins(team, carrier, x, y, pid)
                continue
            ex, ey = result["end"]
            towards_goal = self._prog(ex, team) >= DEC["final_third"] + 10  # a ball into the box often runs out
            if result["back"] or self.rng.random() < (DEC["out_near_goal"] if towards_goal else 0.50):
                restart = self._out_of_play(team, ex, ey) if self.t + 16 < limit else None
                if restart is not None:
                    self.t = arrival + self.rng.uniform(*RESTART_PAUSE_S.get(restart.kind, (6, 14)))
                    return restart
            return self._loose_ball(opp, ex, ey, passed_at, arrival)

    def _release(self, carrier: str, prog: float) -> float:
        """How often the carrier lets the ball go before the presser arrives: more with a good passer, in
        his own half and for defenders; less for forwards who like to hold it up."""
        position = self.roster.players[carrier].position
        zone = 1.25 if prog < 35 else 0.8 if prog >= DEC["final_third"] else 1.0
        role = {"POR": 1.4, "DFC": 1.25, "LD": 1.1, "LI": 1.1, "MCD": 1.1, "DC": 0.75, "ED": 0.85, "EI": 0.85}
        return clip(DEC["release"] * self._skill(carrier, "vision") * zone * role.get(position, 1.0), 0.1, 0.9)

    def _hold(self, team: str, x: float, y: float, carrier: str | None, pid: int, set_piece: str | None) -> None:
        """No time left before the next moment (a substitution): play goes on from here afterwards,
        with the set piece still to be taken if there was one."""
        self.pending = Resume(set_piece or "continue", team, x, y, carrier, pid)
        return None

    def _run_period(self, period: int, end_t: int, resume: Resume) -> None:
        """As the scripted generator, but after a substitution play resumes where it stopped."""
        self.period = period
        while self.t < end_t - 4:
            beat = self.beats[0] if self.beats and self.beats[0]["start"] < end_t else None
            if beat is None:
                self._maybe_free_substitution()
                beat = self.beats[0] if self.beats and self.beats[0]["start"] < end_t else None
            limit = (beat["start"] - 2) if beat else end_t - 3
            self.pending = None
            while self.t < limit - 4:
                nxt = self._possession(resume, limit)
                if nxt is None:
                    resume = self.pending or resume
                    break
                resume = nxt
            if beat is None:
                break
            self.beats.pop(0)
            self.t = max(self.t, beat["start"])
            resume = self._insert_beat(beat, resume)

    def _loose_ball(self, opp: str, ex: float, ey: float, passed_at: float, arrival: float) -> Resume:
        """The nearest rival goes for the misplaced pass and wins it when he can really get there."""
        self.ball_xy = (ex, ey)
        winner = self._pick(opp, ex, ey, weight_key="recover")
        reach = distance(self._where(winner), [ex, ey]) / DEC["loose_speed"]
        self.t = max(arrival, passed_at + reach) + self.rng.uniform(0.2, 0.8)
        return Resume("recovery", opp, ex, ey, winner)

    def _off_ball_run(self, team: str, opp: str, runner: str, pid: int) -> tuple | None:
        rx, ry = self._where(runner)
        end_x = self._to_x(min(self._prog(rx, team) + 8 * self._skill(runner, "ritmo"), DEC["deepest_run"]), team)
        end_y = clip(ry + self.rng.gauss(0, 6), 1, 67)
        speed = round(self.rng.uniform(22, 31) * self._skill(runner, "ritmo") ** 0.5, 1)
        dragged = self._pick(opp, rx, ry, positions=("DFC", "LD", "LI", "MCD")) if self.rng.random() < DEC["run_drags"] else None
        extra, space = {}, None
        if dragged:
            back = 1.0 if team == self.home else -1.0
            towards_centre = 1.0 if ry < PITCH_WIDTH / 2 else -1.0
            dx, dy = self._where(dragged)
            space = round(self.rng.uniform(3.0, 8.5), 1)
            extra = {"dragged_defender_start": [round(clip(dx, 1, 104), 1), round(clip(dy, 1, 67), 1)],
                     "dragged_defender_end": [round(clip(end_x + back * 1.5, 1, 104), 1),
                                              round(clip(end_y + towards_centre * 1.0, 1, 67), 1)]}
        self._emit("off_ball_run", team, runner, [round(rx, 1), round(ry, 1)], [round(end_x, 1), round(end_y, 1)],
                   speed=speed, pid=pid, dragged_defender=dragged, space_opened_m=space, **extra)
        if self.rng.random() < GEN["run_gets_ball"] * self._skill(runner, "sin_balon"):
            self.t += 0.6 * distance([rx, ry], [end_x, end_y]) / (speed / 3.6)
            return (runner, end_x, end_y)
        if dragged and self.rng.random() < DEC["decoy_pass"]:
            # a decoy: the ball goes into the space the dragged defender left, to the team-mate nearest to it
            hole = extra["dragged_defender_start"]
            mate = self._pick(team, hole[0], hole[1], weight_key="receive", exclude=("POR",), exclude_names=(runner,))
            if mate:
                self.t += 0.5 * distance([rx, ry], [end_x, end_y]) / (speed / 3.6)
                return (mate, hole[0], hole[1])
        return None

    def _in_box(self, x: float, y: float, team: str) -> bool:
        """Inside the box ``team`` attacks, on the coordinates as the event will carry them (0.1 m)."""
        return in_box(self._prog(round(x, 1), team), round(y, 1))

    def _foul_factor(self, defending: str, box: bool) -> float:
        return self._aggression(defending) * (DEC["foul_box"] if box else 1.0)

    def _carry(self, team: str, carrier: str, x: float, y: float, under: bool, opp_style: dict,
               arrival: float, far: bool = False) -> tuple[float, float]:
        prog = self._prog(x, team)
        if self.roster.players[carrier].position == "POR":
            longest = 3.0
        elif under:
            longest = GEN["carry_pressed_max"]
        else:
            room = 1.0 if far else 0.45 if prog > 75 else 0.7 if prog > 60 else 1.0
            ability = (self._skill(carrier, "ritmo") + self._skill(carrier, "regate")) / 2
            longest = min(GEN["carry_max"] * room * ability * clip(1.15 - opp_style["press"], 0.5, 1.1),
                          GEN["carry_max"])
        metres = self.rng.uniform(0.0 if under else 2.0, longest)
        angle = self.rng.gauss(0.0, 0.45)
        if abs(y - PITCH_WIDTH / 2) > 24:
            angle += -0.4 if (y > PITCH_WIDTH / 2) == (team == self.home) else 0.4
        new_prog = clip(prog + metres * math.cos(angle), 2.0, max(prog, DEC["deepest_carry"]))
        side = 1.0 if team == self.home else -1.0
        new_y = clip(y + side * metres * math.sin(angle), 2.0, PITCH_WIDTH - 2.0)
        need = distance([x, y], [self._to_x(new_prog, team), new_y]) / self.rng.uniform(4.5, 6.5)
        self.t += max(0.0, need - max(0.0, self.t - arrival))
        return round(self._to_x(new_prog, team), 1), round(new_y, 1)

    # ============================================================ passing
    def _pass(self, team, carrier, x, y, under, pid, style, set_piece: str | None = None,
              run_target: tuple | None = None, quick: bool = False) -> dict:
        prog = self._prog(x, team)
        if set_piece in ("throw_in", "corner", "kickoff"):
            return self._set_piece_pass(team, carrier, x, y, pid, set_piece)
        if run_target is not None and (run_target[0] == carrier or run_target[0] not in self.active[team]):
            run_target = None
        if run_target is None and not set_piece and prog > 86:
            run_target = self._better_placed(team, carrier, x, y, under)
        lines_form = self._form(carrier, "pass_lines")
        back = GEN["backpass"] + (GEN["backpass_pressure"] if under and not quick else 0.0)
        is_back = (run_target is None and prog < GEN["backpass_max_prog"]
                   and self.roster.players[carrier].position != "POR" and self.rng.random() < back)
        if is_back:
            dp = self.rng.uniform(4, 9) - prog
            target_y = clip(34 + self.rng.gauss(0, 6), 2, 66)
        elif prog > 86:  # nobody better placed: keep it, short and towards the middle
            dp = self.rng.gauss(-5, 4)
            target_y = clip(y + 0.4 * (34 - y) + self.rng.gauss(0, 8), 2, 66)
        elif quick:  # released early: short and safe, to the nearest option
            dp = self.rng.gauss(1, 7)
            target_y = clip(y + self.rng.gauss(0, 10), 2, 66)
        else:
            dp = self.rng.gauss(-1 + 10 * style["directness"] * lines_form, 10)
            if prog < 20:
                dp += 8
            if set_piece == "goal_kick":
                dp += 12
            target_y = clip(y + self.rng.gauss(0, 14), 2, 66)
        target_p = clip(prog + dp, 2, DEC["deepest_pass"])
        tx = self._to_x(target_p, team)
        exclude = () if target_p < 15 else ("POR",)
        receiver = self._pick(team, tx, target_y, weight_key="receive", exclude=exclude, exclude_names=(carrier,))
        rx, ry = self._spot(receiver)
        ex = clip(0.7 * tx + 0.3 * rx + self.rng.gauss(0, 2), 0.5, 104.5)
        ey = clip(0.7 * target_y + 0.3 * ry + self.rng.gauss(0, 2), 0.5, 67.5)
        if run_target is not None:
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
        cross = self._prog(ex, team) >= 90 and (y < 18 or y > 50) and (20 < ey < 48)
        pressed = DEC["quick_pass_hard"] if quick else DEC["held_pass_hard"]
        hard = (0.3 * min(dist / 40, 1) + pressed * under + 0.25 * min(lines / 2, 1) + DEC["cross_hard"] * cross
                + 0.2 * clip(progress / 30, 0, 1) + 0.25 * in_box(self._prog(ex, team), ey)
                + DEC["final_third_hard"] * (prog >= DEC["final_third"]))
        success = clip(style["pass_acc"] + 0.10 - 0.35 * hard + 0.3 * (self._skill(carrier, "vision") - 1.0),
                       0.3, 0.98)
        if is_back:
            success = GEN["backpass_success"]
        if set_piece in ("free_kick", "keeper"):
            success = clip(success + 0.08, 0.3, 0.98)
        complete = self.rng.random() < success
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

    def _better_placed(self, team: str, carrier: str, x: float, y: float, under: bool) -> tuple | None:
        """Near goal, the team-mate with a clearly better chance, if the passer sees him."""
        mine = expected_goals(self._prog(x, team), y, under, False)
        best = None
        for name in sorted(self.active[team]):
            if name == carrier or self.roster.players[name].position == "POR":
                continue
            sx, sy = self._spot(name)
            sp = self._prog(sx, team)
            if sp < 80:
                continue
            chance = expected_goals(sp, sy, self.rng.random() >= DEC["free_in_box"], False)
            if chance >= mine + DEC["square_margin"] and (best is None or chance > best[1]):
                best = (name, chance, sx, sy)
        if best and self.rng.random() < DEC["square_prob"] * self._skill(carrier, "vision"):
            return (best[0], best[2], best[3])
        return None

    # ============================================================ shots and penalties
    def _shot(self, team, shooter, x, y, under, pid, cross, xg: float | None = None,
              set_piece: str | None = None) -> Resume:
        opp = self.roster.opponent(team)
        prog = self._prog(x, team)
        if xg is None:
            xg = expected_goals(prog, y, under, cross)
        accuracy = DEC["accuracy"] + 0.5 * xg + 0.2 * (self._skill(shooter, "disparo") - 1.0)
        blocked_share = DEC["blocked_crowded"] if under else 0.3
        if self.rng.random() < xg:  # the score never changes this: a shot goes in with its xG
            outcome = "goal"
        elif set_piece == "penalty":
            outcome = "saved" if self.rng.random() < 0.6 else "off_target"
        elif self.rng.random() < accuracy:
            outcome = "saved"
        else:
            outcome = "blocked" if self.rng.random() < blocked_share else "off_target"
        goal_x = PITCH_LENGTH if team == self.home else 0.0
        end_y = clip(34 + self.rng.gauss(0, 2.5 if outcome in ("goal", "saved") else 7), 0, 68)
        if outcome == "off_target" and abs(end_y - 34) < 4:
            end_y = 34 + (5 if end_y >= 34 else -5)
        end = [goal_x, round(end_y, 1)] if outcome != "blocked" else \
            [round(clip(x + (3 if team == self.home else -3), 0, 105), 1), round(y, 1)]
        extra = {"set_piece": set_piece} if set_piece else {}
        self._emit("shot", team, shooter, [round(x, 1), round(y, 1)], end, outcome=outcome,
                   speed=round(clip(self.rng.gauss(94, 9), 60, 124), 1), under=under, pid=pid, xg=xg, **extra)
        if outcome == "goal":
            side = "home" if team == self.home else "away"
            self.scoreline[side] += 1
            self._emit("goal", team, shooter, [round(x, 1), round(y, 1)], pid=pid,
                       assist=None if set_piece == "penalty" else self._last_passer(pid, shooter),
                       scoreline=dict(self.scoreline))
            self.last_goal_t = self.t
            self.t += self.rng.uniform(35, 50)
            return Resume("kickoff", opp)
        if outcome == "blocked":
            self.t += self.rng.uniform(1, 2)
            if self.rng.random() < GEN["corner_after_block"]:
                self.t += self.rng.uniform(10, 16)
                return self._corner_for(team, y)
            self.ball_xy = (x, y)
            return Resume("recovery", opp, x, y, self._pick(opp, x, y, positions=("DFC", "MCD", "LD", "LI")))
        if outcome == "saved" and self.rng.random() < GEN["corner_after_save"]:
            self.t += self.rng.uniform(10, 16)
            return self._corner_for(team, end_y)
        self.t += self.rng.uniform(4, 6) if outcome == "saved" else self.rng.uniform(*RESTART_PAUSE_S["goal_kick"])
        return Resume("keeper" if outcome == "saved" else "goal_kick", opp)

    def _penalty(self, team: str, pid: int, limit: float) -> Resume:
        """A foul inside the box: the best finisher on the pitch shoots from the spot."""
        self.t = min(self.t + self.rng.uniform(*DEC["penalty_pause"]), max(self.t + 20.0, limit - 3.0))
        taker = max((n for n in sorted(self.active[team]) if self.roster.players[n].position != "POR"),
                    key=lambda n: self._card(n).get("disparo", 50))
        x, y = self._to_x(PENALTY_SPOT_PROG, team), PITCH_WIDTH / 2
        self.ball_xy = (x, y)
        return self._shot(team, taker, x, y, False, pid, cross=False, xg=DEC["penalty_xg"], set_piece="penalty")
