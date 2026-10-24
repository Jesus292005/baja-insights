import helpers  # noqa: F401  (puts src/ on sys.path)
import unittest

from baja_insights.generator import DEMO_SEED, generate_match
from helpers import roster, validator


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


if __name__ == "__main__":
    unittest.main()
