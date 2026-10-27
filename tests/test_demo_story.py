"""The demo match m001 must keep its scripted moments: the 1-1 at 17 and 63 and the equalizer chain.

Agreed on 27 October 2026: only the moments the script inserts as written are kept, because the goal
analysis, the notices and the video use them. Who leads the MVP race, who wins it, the duels, the phases
and the verdict depend on the seed and may change with the generator.
"""

import helpers  # noqa: F401  (puts src/ on sys.path)
import unittest

from baja_insights.engine import InsightEngine
from baja_insights.generator import DEMO_SEED, generate_match
from helpers import MOCKS, load, roster


class DemoStoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = generate_match(roster(), seed=DEMO_SEED, script="m001")
        engine = InsightEngine(roster())
        cls.first_at_35 = None
        for event in cls.events:
            if cls.first_at_35 is None and event["t_s"] > 35 * 60:
                cls.first_at_35 = engine.state.ranking()[0][0]
            engine.process(event)
        cls.insights = engine.insights
        cls.mock = {i["insight_id"]: i for i in load(MOCKS / "insights_sample.json")}

    def of(self, kind):
        return [i for i in self.insights if i["type"] == kind]

    def test_one_one_with_goals_at_17_and_63(self):
        goals = [(e["minute"], e["team"]) for e in self.events if e["type"] == "goal"]
        self.assertEqual(goals, [(17, "Real Cardón"), (63, "Bahía FC")])

    def test_equalizer_chain_and_invisible_assist_match_the_mock(self):
        chain = self.of("goal_chain")[1]["facts"]
        expected = self.mock["i11"]["facts"]
        self.assertEqual([(l["player"], l["action"], l["credit"]) for l in chain["chain"]],
                         [(l["player"], l["action"], l["credit"]) for l in expected["chain"]])
        self.assertEqual(chain["invisible_assist"]["player"], "J. Torres")

    def test_equalizer_chain_can_be_drawn(self):
        """Every link carries the event's coordinates, and the off-ball run also the dragged centre-back,
        moved by the space the run opened. This is what the pitch of the goal analysis draws."""
        chain = self.of("goal_chain")[1]["facts"]["chain"]
        by_id = {e["event_id"]: e for e in self.events}
        for link in chain:
            event = by_id[link["event_id"]]
            self.assertEqual((link["start"], link["end"]), (event["start"], event["end"]), link["player"])
        run = next(l for l in chain if l["type"] == "off_ball_run")
        self.assertEqual(run["dragged_defender"], "G. Cárdenas")
        dx = run["dragged_defender_end"][0] - run["dragged_defender_start"][0]
        dy = run["dragged_defender_end"][1] - run["dragged_defender_start"][1]
        space = self.mock["i11"]["facts"]["invisible_assist"]["space_opened_m"]
        self.assertAlmostEqual((dx * dx + dy * dy) ** 0.5, space, delta=0.05)


if __name__ == "__main__":
    unittest.main()
