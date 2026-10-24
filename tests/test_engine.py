"""The engine run over the hand-written mock events must reproduce the mock story."""

import helpers  # noqa: F401  (puts src/ on sys.path)
import unittest

from baja_insights.engine import InsightEngine
from baja_insights.engine.tools import MatchQuery
from helpers import DATA, MOCKS, load, roster


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


class MvpRankingTest(unittest.TestCase):
    """Contract v1.1: mvp_rank_change.facts.ranking is the top of the MVP right after the change."""

    @classmethod
    def setUpClass(cls):
        from baja_insights.engine import params

        cls.top = params.MVP_RANKING_TOP
        events = load(DATA / "m001" / "events.jsonl")
        cls.insights = InsightEngine(roster()).run(events)
        cls.query = MatchQuery(events, roster())
        cls.changes = [i for i in cls.insights if i["type"] == "mvp_rank_change"]

    def test_every_change_carries_the_top(self):
        self.assertTrue(self.changes)
        for insight in self.changes:
            facts = insight["facts"]
            ranking = facts["ranking"]
            self.assertEqual(len(ranking), self.top, insight["insight_id"])
            self.assertEqual([r["rank"] for r in ranking], list(range(1, self.top + 1)))
            scores = [r["mvp_score"] for r in ranking]
            self.assertEqual(scores, sorted(scores, reverse=True))
            announced = ranking[facts["to_rank"] - 1]
            self.assertEqual((announced["player"], announced["mvp_score"]), (facts["player"], facts["mvp_score"]))
            self.assertEqual(ranking[0]["player"], facts.get("leader", facts["player"]))

    def test_same_shape_as_the_chat_function(self):
        sample = self.query.get_mvp_ranking("45:00", self.top)["ranking"]
        for insight in self.changes:
            for row, chat_row in zip(insight["facts"]["ranking"], sample):
                self.assertEqual(set(row), set(chat_row))

    def test_matches_the_chat_function_when_nothing_else_happens_that_second(self):
        events = load(DATA / "m001" / "events.jsonl")
        per_second = {}
        for e in events:
            per_second[e["t_s"]] = per_second.get(e["t_s"], 0) + 1
        checked = 0
        for insight in self.changes:
            if per_second[insight["t_s"]] > 1:
                continue  # the insight is a snapshot after its trigger event, not after the whole second
            at = f"{insight['t_s'] // 60:02d}:{insight['t_s'] % 60:02d}"
            self.assertEqual(insight["facts"]["ranking"], self.query.get_mvp_ranking(at, self.top)["ranking"])
            checked += 1
        self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main()
