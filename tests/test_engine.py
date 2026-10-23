"""The engine run over the hand-written mock events must reproduce the mock story."""

import helpers  # noqa: F401  (puts src/ on sys.path)
import unittest

from baja_insights.engine import InsightEngine
from helpers import MOCKS, load, roster


def run_mock():
    return InsightEngine(roster()).run(load(MOCKS / "events_sample.json"))


class MockStoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.insights = run_mock()
        cls.mock = {i["insight_id"]: i for i in load(MOCKS / "insights_sample.json")}

    def by_type(self, kind):
        return [i for i in self.insights if i["type"] == kind]

    def test_goal_chains_match_mocks(self):
        chains = {i["t_s"]: i["facts"] for i in self.by_type("goal_chain")}
        for mock_id in ("i02", "i11"):
            expected = self.mock[mock_id]["facts"]
            actual = chains[self.mock[mock_id]["t_s"]]
            self.assertEqual(actual["chain"], expected["chain"])
            self.assertEqual(actual["invisible_assist"], expected["invisible_assist"])
            self.assertEqual(actual["duration_s"], expected["duration_s"])
            self.assertEqual(actual["scoreline"], expected["scoreline"])
            self.assertEqual(actual["assist"], expected["assist"])

    def test_torres_takes_first_place_with_defense_card(self):
        hits = [i for i in self.by_type("mvp_rank_change") if i["t_s"] == 2020]
        self.assertEqual(len(hits), 1)
        facts = hits[0]["facts"]
        self.assertEqual((facts["player"], facts["to_rank"]), ("J. Torres", 1))
        self.assertEqual(facts["card_change"], self.mock["i05"]["facts"]["card_change"])
        self.assertEqual(facts["recoveries_window"], "24:10-33:40")
        self.assertEqual(hits[0]["evidence"], [531, 642, 739])

    def test_salgado_vision_card(self):
        card = [i for i in self.by_type("card_upgrade") if i["t_s"] == 2052][0]["facts"]
        expected = self.mock["i06"]["facts"]
        for key in ("player", "attribute", "from", "to", "delta", "reason", "pass_distance_m",
                    "pass_difficulty", "led_to", "led_to_event_id"):
            self.assertEqual(card[key], expected[key], key)

    def test_invisible_assist_card(self):
        card = [i for i in self.by_type("card_upgrade") if i["players"] == ["J. Torres"]
                and i["facts"]["attribute"] == "sin_balon"][0]
        expected = self.mock["i12"]["facts"]
        self.assertEqual({k: card["facts"][k] for k in expected}, expected)

    def test_first_duel_goes_to_verdugo(self):
        duel = self.by_type("duel_state")[0]
        self.assertEqual(duel["t_s"], self.mock["i01"]["t_s"])
        self.assertEqual(duel["evidence"], self.mock["i01"]["evidence"])
        self.assertLess(duel["facts"]["bar"], 0)
        self.assertEqual((duel["facts"]["duels_won_a"], duel["facts"]["duels_won_b"]), (0, 1))

    def test_ids_are_sequential_and_deterministic(self):
        again = run_mock()
        self.assertEqual(again, self.insights)
        self.assertEqual([i["insight_id"] for i in again], [f"i{n:02d}" for n in range(1, len(again) + 1)])

    def test_full_time_insights(self):
        self.assertEqual(len(self.by_type("top3")), 1)
        summary = self.by_type("match_summary")[0]["facts"]
        self.assertEqual(summary["final_scoreline"], {"home": 1, "away": 1})
        self.assertEqual([g["event_id"] for g in summary["goals"]], [393, 1357])

    def test_keys_never_predict(self):
        keys = self.by_type("match_keys")[0]["facts"]
        self.assertIs(keys["no_prediction"], True)
        self.assertNotIn("win_probability", keys)


if __name__ == "__main__":
    unittest.main()
