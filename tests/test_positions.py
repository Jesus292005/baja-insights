"""Illustrative positions of the 22 players: anchored to the events, physically possible, and in the
right shape at every set piece. They are only for drawing: nothing else reads them."""

import helpers  # noqa: F401  (puts src/ on sys.path)
import math
import unittest

from baja_insights.generator import DEMO_SEED, generate_match
from baja_insights.positions import HZ, build_positions
from helpers import CONTRACTS, load, roster, validator

HOME = "Bahía FC"


def lineup(pos, side, t):
    names = [p["player"] for p in pos["teams"][side]["players"]]
    for c in pos["lineup_changes"]:
        if c["team"] == side and c["t_s"] <= t:
            names[c["slot"]] = c["player_in"]
    return names


def where(pos, name, t):
    f = pos["frames"][int(round(t * HZ))]
    for side, key in (("home", "h"), ("away", "a")):
        names = lineup(pos, side, f["t"])
        if name in names:
            return f[key][names.index(name)]
    return None


def prog(x, team):
    return x if team == HOME else 105 - x


class DemoPositionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = generate_match(roster(), seed=DEMO_SEED, script="m001")
        cls.pos = build_positions(cls.events, roster(), "m001")

    def test_shape_of_the_file(self):
        p = self.pos
        self.assertTrue(p["illustrative"])
        self.assertEqual(len(p["frames"]), 90 * 60 * HZ + 1)
        for f in p["frames"][:: 97]:
            self.assertEqual((len(f["h"]), len(f["a"])), (11, 11))
            for x, y in f["h"] + f["a"] + [f["b"]]:
                self.assertTrue(-2 <= x <= 107 and -2 <= y <= 70)
        self.assertEqual([q["rotate_180"] for q in p["periods"]], [False, True])

    def test_matches_the_schema(self):
        v = validator("positions")
        if v is None:
            self.skipTest("jsonschema not installed")
        self.assertEqual([e.message for e in v.iter_errors(self.pos)][:3], [])

    def test_deterministic(self):
        self.assertEqual(build_positions(self.events, roster(), "m001")["frames"][::500], self.pos["frames"][::500])

    def test_the_player_of_every_event_is_where_it_happened(self):
        far = []
        for e in self.events:
            if not e.get("start") or not e.get("player") or e["type"] == "goal":
                continue
            p = where(self.pos, e["player"], e["t_s"])
            if p is not None and math.dist(p, e["start"]) > 1.2:  # defenders stand 1 m goal side of the ball
                far.append((e["event_id"], round(math.dist(p, e["start"]), 1)))
        self.assertLessEqual(len(far), 3, far)

    def test_the_ball_is_where_every_action_happened(self):
        # events carry whole seconds: two actions in the same second at different spots cannot both hold
        spots = {}
        for e in self.events:
            if e.get("start") and e.get("player") and e["type"] not in ("off_ball_run", "goal"):
                spots.setdefault(e["t_s"], set()).add(tuple(e["start"]))
        far = [e["event_id"] for e in self.events if e.get("start") and e.get("player") and e["type"] != "off_ball_run"
               and len(spots.get(e["t_s"], ())) == 1
               and math.dist(self.pos["frames"][e["t_s"] * HZ]["b"], e["start"]) > 1.0]
        self.assertLessEqual(len(far), 2, far)

    def test_the_ball_stays_at_the_foot_of_who_carries_it(self):
        """Between receiving a pass and his next action, the ball goes with the player, not on its own."""
        play = [e for e in self.events if e.get("start") and e.get("team") and e["type"] != "goal"]
        far = total = 0
        for a, b in zip(play, play[1:]):
            if a["type"] == "pass" and a["outcome"] == "complete" and b["player"] == a["receiver"] \
                    and b["type"] not in ("pressure", "tackle", "foul"):
                v = max((a.get("speed_kmh") or 50) / 3.6, 5)
                arrive = a["t_s"] + min(math.dist(a["start"], a["end"]) / v, 3)
                for k in range(int(math.ceil(arrive * HZ)) + 1, int(b["t_s"] * HZ)):
                    total += 1
                    far += math.dist(self.pos["frames"][k]["b"], where(self.pos, b["player"], k / HZ)) > 1.0
        self.assertGreater(total, 500)
        self.assertEqual(far, 0)

    def test_receivers_meet_the_ball(self):
        """At the instant the ball arrives (between two frames), the receiver is there. He may already be
        a little past it, because he carries the ball on, so the bar is 3 m for 90% of passes."""
        n, far = 0, 0
        for e in self.events:
            if e["type"] == "pass" and e["outcome"] == "complete" and e.get("receiver"):
                v = max((e.get("speed_kmh") or 50) / 3.6, 5)
                arrive = e["t_s"] + min(math.dist(e["start"], e["end"]) / v, 3)
                k = int(math.floor(arrive * HZ))
                p0, p1 = where(self.pos, e["receiver"], k / HZ), where(self.pos, e["receiver"], (k + 1) / HZ)
                if p0 is None or p1 is None:
                    continue
                w = arrive * HZ - k
                p = (p0[0] + (p1[0] - p0[0]) * w, p0[1] + (p1[1] - p0[1]) * w)
                n += 1
                far += math.dist(p, e["end"]) > 3.0
        self.assertLess(far / n, 0.10)

    def test_the_carrier_is_pressed_and_team_mates_do_not_overlap(self):
        """The nearest rival closes the player on the ball to a few metres, and team-mates keep the width
        of a disc on screen (3.6 m) apart outside set pieces."""
        home = HOME
        play = [e for e in self.events if e.get("start") and e.get("team") and e["type"] != "goal"]
        near = []
        for a, b in zip(play, play[1:]):
            if a["type"] == "pass" and a["outcome"] == "complete" and b["player"] == a["receiver"] \
                    and b["type"] in ("pass", "shot"):
                v = max((a.get("speed_kmh") or 50) / 3.6, 5)
                arrive = a["t_s"] + min(math.dist(a["start"], a["end"]) / v, 3)
                for k in range(int(math.ceil(arrive * HZ)) + 1, int(b["t_s"] * HZ)):
                    f = self.pos["frames"][k]
                    rivals = f["a"] if a["team"] == home else f["h"]
                    near.append(min(math.dist(f["b"], p) for p in rivals[1:]))
        near.sort()
        self.assertTrue(2.5 <= near[len(near) // 2] <= 5.0, near[len(near) // 2])
        dead = [(sp["ball_out_from_t_s"], sp["t_s"]) for sp in self.pos["set_pieces"]]
        runs, close = 0, {}
        for f in self.pos["frames"]:
            if any(a <= f["t"] <= b for a, b in dead):
                close = {}
                continue
            for key in ("h", "a"):
                pts = f[key]
                for i in range(11):
                    for j in range(i + 1, 11):
                        if math.dist(pts[i], pts[j]) < 3.6:
                            close[(key, i, j)] = close.get((key, i, j), 0) + 1
                        elif close.pop((key, i, j), 0) >= 4:
                            runs += 1
        self.assertLessEqual(runs, 10)

    def test_nobody_runs_faster_than_a_sprinter(self):
        fast, total, prev = 0, 0, {}
        for f in self.pos["frames"]:
            if f["t"] == 2700.0:  # half time: everybody comes out in the kick-off shape
                prev = {}
            for side, key in (("home", "h"), ("away", "a")):
                for name, p in zip(lineup(self.pos, side, f["t"]), f[key]):
                    if name in prev:
                        total += 1
                        fast += math.dist(p, prev[name]) * HZ > 9.5
                    prev[name] = p
        self.assertLess(fast / total, 0.001)

    def test_the_equalizer_shows_the_run_and_the_dragged_centre_back(self):
        run = next(e for e in self.events if e["type"] == "off_ball_run" and e["player"] == "J. Torres"
                   and e.get("dragged_defender") == "G. Cárdenas" and e["minute"] == 62)
        played = next(e for e in self.events if e["t_s"] > run["t_s"] and e["type"] == "pass")
        self.assertLess(math.dist(where(self.pos, "J. Torres", played["t_s"]), run["end"]), 1.5)
        self.assertLess(math.dist(where(self.pos, "G. Cárdenas", played["t_s"]), run["dragged_defender_end"]), 1.5)

    def test_bahia_defends_higher_when_it_presses(self):
        """team_phase pressure_shift: Bahía's back line without the ball is higher after the 48th minute."""
        owner, i, heights = None, 0, {"first": [], "press": []}
        play = [e for e in self.events if e.get("team") and e.get("start") and e["type"] not in ("pressure", "tackle", "foul")]
        for f in self.pos["frames"]:
            while i < len(play) and play[i]["t_s"] <= f["t"]:
                owner = play[i]["team"]
                i += 1
            if owner != HOME:
                window = "first" if f["t"] < 2700 else "press" if 4020 <= f["t"] < 4620 else None
                if window:
                    heights[window].append(sum(f["h"][s][0] for s in (1, 2, 3, 4)) / 4)
        first, press = (sum(v) / len(v) for v in (heights["first"], heights["press"]))
        self.assertGreater(press, first + 8, (first, press))

    def test_set_pieces(self):
        by_kind = {}
        for sp in self.pos["set_pieces"]:
            by_kind.setdefault(sp["kind"], []).append(sp)
        self.assertTrue({"kickoff", "throw_in", "corner", "goal_kick", "free_kick", "keeper"} <= set(by_kind), set(by_kind))
        name_of = {"home": HOME, "away": "Real Cardón"}
        for sp in self.pos["set_pieces"]:
            f = self.pos["frames"][int(sp["t_s"] * HZ)]
            team = name_of[sp["team"]]
            mine, theirs = (f["h"], f["a"]) if sp["team"] == "home" else (f["a"], f["h"])
            with self.subTest(kind=sp["kind"], t=sp["t_s"]):
                self.assertLess(math.dist(where(self.pos, sp["taker"], sp["t_s"]), sp["spot"]), 1.0)
                if sp["kind"] == "kickoff":
                    self.assertTrue(all(prog(x, team) <= 53 for x, _ in mine))
                    self.assertTrue(all(prog(x, team) >= 52 for x, _ in theirs))
                if sp["kind"] == "goal_kick":  # the rivals wait outside the box
                    self.assertTrue(all(prog(x, team) >= 16.5 or abs(y - 34) > 20.16 for x, y in theirs[1:]))
                if sp["kind"] == "free_kick" and sp["t_s"] - sp["ball_out_from_t_s"] >= 10:
                    before = self.pos["frames"][int(sp["t_s"] * HZ) - 1]  # half a second before the kick
                    rivals = before["a"] if sp["team"] == "home" else before["h"]
                    self.assertGreaterEqual(min(math.dist(p, sp["spot"]) for p in rivals[1:]), 8.0)  # 9.15 m, less near a touchline
                if sp["kind"] == "corner" and sp["t_s"] - sp["ball_out_from_t_s"] >= 9:
                    in_box = sum(prog(x, team) >= 88.5 and abs(y - 34) <= 20.16 for x, y in mine)
                    self.assertGreaterEqual(in_box, 5)

    def test_teams_change_ends_on_screen_at_half_time(self):
        first, second = self.pos["periods"]
        self.assertEqual((first["home_attacks"], second["home_attacks"]), ("right", "left"))
        self.assertEqual(second["from_t_s"], 2700)


class FreeMatchPositionsTest(unittest.TestCase):
    def test_a_free_match_works_too(self):
        events = generate_match(roster(), seed=3, script=None)
        pos = build_positions(events, roster(), None)
        self.assertEqual(len(pos["frames"]), 90 * 60 * HZ + 1)
        far = sum(1 for e in events if e.get("start") and e.get("player") and e["type"] != "goal"
                  and (p := where(pos, e["player"], e["t_s"])) is not None and math.dist(p, e["start"]) > 1.2)
        self.assertLessEqual(far, 5)

    def test_the_data_file_is_up_to_date(self):
        data = load(CONTRACTS.parent / "data" / "m001" / "positions.json")
        events = load(CONTRACTS.parent / "data" / "m001" / "events.jsonl")
        self.assertEqual(build_positions(events, roster(), "m001")["frames"][::700], data["frames"][::700])


if __name__ == "__main__":
    unittest.main()
