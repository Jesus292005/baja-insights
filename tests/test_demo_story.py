"""The demo match m001 must keep the story the video, the pitch and the mocks tell.

If a change to the generator, the engine or the script breaks one of these, the change is wrong
or the story has to be agreed again with the team. Do not just update the expected values.
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

    def test_torres_leads_at_35_and_wins_the_mvp(self):
        self.assertEqual(self.first_at_35, "J. Torres")  # "¿Por qué Torres va primero?" at 35:00
        # the MVP race on screen (ranking of the last update before 35:00) also has him first
        before = [i for i in self.of("mvp_rank_change") if i["t_s"] <= 35 * 60]
        self.assertEqual(before[-1]["facts"]["ranking"][0]["player"], "J. Torres")
        self.assertEqual(self.of("top3")[0]["facts"]["top3"][0]["player"], "J. Torres")

    def test_who_really_won(self):
        verdict = self.of("match_summary")[0]["facts"]["who_really_won"]
        self.assertTrue(verdict.startswith("Bahía FC generó más peligro"), verdict)

    def test_phases(self):
        phases = [(i["team"], i["facts"]["label"], i["t_s"] // 60) for i in self.of("team_phase")]
        self.assertTrue(any(t == "Real Cardón" and label == "control" and m < 45 for t, label, m in phases), phases)
        self.assertTrue(any(t == "Bahía FC" and label == "pressure_shift" and m >= 45 for t, label, m in phases), phases)


if __name__ == "__main__":
    unittest.main()
