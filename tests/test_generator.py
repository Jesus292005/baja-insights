import helpers  # noqa: F401  (puts src/ on sys.path)
import unittest

from baja_insights.generator import DEMO_SEED, generate_match
from helpers import MOCKS, load, roster, validator


class ScriptedMatchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = generate_match(roster(), seed=DEMO_SEED, script="m001")

    def test_deterministic(self):
        self.assertEqual(generate_match(roster(), seed=DEMO_SEED, script="m001"), self.events)

    def test_story_beats_are_kept(self):
        goals = [(e["t_s"], e["player"], e["scoreline"]) for e in self.events if e["type"] == "goal"]
        self.assertEqual(goals, [(1060, "S. Leyva", {"home": 0, "away": 1}),
                                 (3789, "M. Ramírez", {"home": 1, "away": 1})])
        runs = [e for e in self.events if e["type"] == "off_ball_run" and e.get("dragged_defender") == "G. Cárdenas"]
        self.assertTrue(any(e["player"] == "J. Torres" and e["t_s"] == 3778 for e in runs))
        self.assertEqual(self.events[-1]["type"], "match_end")
        self.assertEqual(self.events[-1]["scoreline"], {"home": 1, "away": 1})

    def test_stream_is_ordered_and_numbered(self):
        ids = [e["event_id"] for e in self.events]
        self.assertEqual(ids, list(range(1, len(ids) + 1)))
        times = [e["t_s"] for e in self.events]
        self.assertEqual(times, sorted(times))
        self.assertTrue(all(e["minute"] * 60 + e["second"] == e["t_s"] for e in self.events))

    def test_realistic_volume(self):
        shots = sum(1 for e in self.events if e["type"] == "shot")
        passes = sum(1 for e in self.events if e["type"] == "pass")
        self.assertTrue(10 <= shots <= 40, shots)
        self.assertTrue(600 <= passes <= 1400, passes)

    def test_events_follow_contract(self):
        v = validator("event")
        if v is None:
            self.skipTest("jsonschema not installed")
        errors = [(e["event_id"], err.message) for e in self.events for err in v.iter_errors(e)]
        self.assertEqual(errors, [])


class FreeMatchTest(unittest.TestCase):
    def test_free_mode_is_consistent_and_seed_dependent(self):
        a = generate_match(roster(), seed=2, script=None)
        b = generate_match(roster(), seed=3, script=None)
        self.assertNotEqual(a, b)
        for events in (a, b):
            goals = [e for e in events if e["type"] == "goal"]
            final = events[-1]["scoreline"]
            self.assertEqual(final["home"] + final["away"], len(goals))


class SetPieceTest(unittest.TestCase):
    """A ball that goes out crosses a line and the rival restarts from the right place, untouched."""

    @classmethod
    def setUpClass(cls):
        cls.matches = [generate_match(roster(), seed=DEMO_SEED, script="m001")] + \
                      [generate_match(roster(), seed=s, script=None) for s in (1, 2, 3)]

    def pairs(self):
        for events in self.matches:
            play = [e for e in events if e.get("start") is not None and e.get("team")]
            yield from zip(play, play[1:])

    def test_every_kind_appears(self):
        kinds = {e.get("set_piece") for events in self.matches for e in events}
        self.assertTrue({"kickoff", "throw_in", "corner", "goal_kick", "free_kick", "keeper"} <= kinds, kinds)

    def test_set_pieces_are_taken_from_the_right_place(self):
        home = roster().home
        for events in self.matches:
            for e in events:
                kind = e.get("set_piece")
                if not kind:
                    continue
                x, y = e["start"]
                prog = x if e["team"] == home else 105 - x
                with self.subTest(kind=kind, event=e["event_id"]):
                    self.assertEqual(e["type"], "pass")
                    if kind == "throw_in":
                        self.assertIn(y, (0.0, 68.0))
                    elif kind == "corner":
                        self.assertEqual((prog, y in (0.0, 68.0)), (105.0, True))
                    elif kind == "goal_kick":
                        self.assertEqual(e["position"], "POR")
                        self.assertLessEqual(prog, 5.5)
                    elif kind == "kickoff":
                        self.assertEqual(e["start"], [52.5, 34.0])

    def test_out_of_play_ends_on_a_line_and_the_rival_restarts_there(self):
        home = roster().home
        checked = 0
        for a, b in self.pairs():
            if not a.get("out_of_play"):
                continue
            checked += 1
            x, y = a["end"]
            self.assertTrue(x in (0.0, 105.0) or y in (0.0, 68.0), a)
            self.assertNotEqual(b["team"], a["team"])
            if y in (0.0, 68.0):
                self.assertEqual((b["set_piece"], b["start"]), ("throw_in", a["end"]))
            else:
                attacked = (x == 105.0) == (a["team"] == home)
                self.assertEqual(b["set_piece"], "goal_kick" if attacked else "corner")
        self.assertGreater(checked, 20)

    def test_a_foul_is_followed_by_the_free_kick(self):
        """Unless a scripted beat of the demo comes first: those are kept exactly as written."""
        beats = {(e["player"], e["type"], tuple(e["start"] or ())) for e in load(MOCKS / "events_sample.json")}
        for a, b in self.pairs():
            if a["type"] == "foul" and (b["player"], b["type"], tuple(b["start"])) not in beats:
                with self.subTest(foul=a["event_id"]):
                    self.assertEqual((b.get("set_piece"), b["team"]),
                                     ("free_kick", roster().players[a["fouled"]].team))


class MovementTest(unittest.TestCase):
    """Players carry the ball, and an off-ball run usually ends with the pass to the runner."""

    @classmethod
    def setUpClass(cls):
        cls.matches = [generate_match(roster(), seed=DEMO_SEED, script="m001")] + \
                      [generate_match(roster(), seed=s, script=None) for s in (1, 2, 3)]

    def test_players_carry_the_ball(self):
        import math
        carries = []
        for events in self.matches:
            play = [e for e in events if e.get("start") and e.get("team") and e["type"] != "goal"]
            for a, b in zip(play, play[1:]):
                if a["type"] == "pass" and a["outcome"] == "complete" and b["player"] == a["receiver"] \
                        and b["type"] in ("pass", "shot") and not b.get("under_pressure"):
                    carries.append(math.dist(a["end"], b["start"]))
        carries.sort()
        self.assertGreaterEqual(carries[len(carries) // 2], 3.0)
        self.assertLessEqual(carries[-1], 16.0)

    def test_runs_end_in_the_pass_to_the_runner(self):
        runs = to_runner = 0
        for events in self.matches:
            play = [e for e in events if e.get("start") and e.get("team") and e["type"] != "goal"]
            for i, e in enumerate(play):
                if e["type"] != "off_ball_run":
                    continue
                runs += 1
                nxt = next((n for n in play[i + 1:] if n["type"] in ("pass", "shot")), None)
                to_runner += bool(nxt and nxt["type"] == "pass" and nxt.get("receiver") == e["player"])
                if e.get("dragged_defender"):
                    self.assertIn("dragged_defender_end", e)
        self.assertGreaterEqual(to_runner / runs, 0.6)


if __name__ == "__main__":
    unittest.main()
