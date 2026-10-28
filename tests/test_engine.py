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

    def test_chain_links_carry_the_event_coordinates(self):
        events = {e["event_id"]: e for e in load(MOCKS / "events_sample.json")}
        for insight in self.by_type("goal_chain"):
            for link in insight["facts"]["chain"]:
                event = events[link["event_id"]]
                self.assertEqual(link["start"], event["start"])
                self.assertEqual(link["end"], event["end"])
                if link["type"] == "off_ball_run":
                    for key in ("dragged_defender", "dragged_defender_start", "dragged_defender_end"):
                        self.assertEqual(link[key], event[key], key)
                else:
                    self.assertNotIn("dragged_defender", link)

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


class CardReasonTest(unittest.TestCase):
    """Card reasons reach fan texts as they are, and fan texts carry one figure at most."""

    def test_every_reason_has_at_most_one_figure(self):
        import re
        from baja_insights.generator import generate_match
        reasons = set()
        matches = [load(DATA / "m001" / "events.jsonl")] + [generate_match(roster(), seed=s, script=None) for s in range(1, 9)]
        for events in matches:
            for i in InsightEngine(roster()).run(events):
                change = i["facts"].get("card_change") or (i["facts"] if i["type"] == "card_upgrade" else None)
                if change:
                    reasons.add(change["reason"])
        self.assertTrue(reasons)
        for reason in reasons:
            self.assertLessEqual(len(re.findall(r"\d+(?:[.,]\d+)?", reason)), 1, reason)


class CardReasonCodeTest(unittest.TestCase):
    """Contract v1.1: every card change says what it is with reason_code and its numbers, for any language."""

    PARAMS = {
        "line_breaking_pass": {"lines", "under_pressure"}, "opp_half_recoveries": {"count", "window_min"},
        "shot_speed": {"speed_kmh"}, "duel_streak": {"count"}, "run_speed": {"speed_kmh"},
        "dribbles": {"count", "window_min"}, "run_ended_in_shot": {"dragged_defender"},
        "run_opened_goal": {"dragged_defender", "dragged_position"}, "standout_defensive": set(),
        "standout_creative": set(), "pass_streak": {"count"}, "recovery_to_shot": {"seconds", "shooter"},
        "big_save": {"xg", "shooter"},
    }

    def test_codes_and_params(self):
        from baja_insights.generator import generate_match
        schema = load(helpers.CONTRACTS / "insight.schema.json")["$defs"]["card_change"]["properties"]
        self.assertEqual(set(schema["reason_code"]["enum"]), set(self.PARAMS))
        seen = set()
        matches = [load(DATA / "m001" / "events.jsonl"), load(MOCKS / "events_sample.json")] + \
            [generate_match(roster(), seed=s, script=None) for s in range(1, 13)]
        for events in matches:
            for i in InsightEngine(roster()).run(events):
                change = i["facts"].get("card_change") or (i["facts"] if i["type"] == "card_upgrade" else None)
                if change:
                    self.assertIn(change["reason_code"], self.PARAMS, change["reason"])
                    self.assertEqual(set(change["reason_params"]), self.PARAMS[change["reason_code"]], change)
                    seen.add(change["reason_code"])
        self.assertGreaterEqual(len(seen), 8, seen)


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


class NewMomentsTest(unittest.TestCase):
    """Long possessions, pass streaks, counter-attacks and big saves: shown once they have happened."""

    @classmethod
    def setUpClass(cls):
        from baja_insights.generator import generate_match
        cls.matches = [load(DATA / "m001" / "events.jsonl")] + [generate_match(roster(), seed=s, script=None) for s in (1, 2, 3, 4)]
        cls.runs = [(events, InsightEngine(roster()).run(events)) for events in cls.matches]

    def each(self, test):
        found = 0
        for events, insights in self.runs:
            by_id = {e["event_id"]: e for e in events}
            for i in insights:
                if test(i):
                    found += 1
                    yield i, by_id
        self.assertGreater(found, 0)

    def test_possession_spell(self):
        for i, by_id in self.each(lambda i: i["type"] == "team_phase" and i["facts"]["label"] == "possession_spell"):
            f = i["facts"]
            passes = [by_id[e] for e in i["evidence"]]
            self.assertGreaterEqual(f["passes"], 12)
            self.assertEqual(len(passes), f["passes"])
            self.assertTrue(all(p["type"] == "pass" and p["outcome"] == "complete" and p["team"] == i["team"] for p in passes))
            self.assertIn(f["ended_in"], ("goal", "shot", "out", "foul", "lost"))
            self.assertGreaterEqual(i["t_s"], max(p["t_s"] for p in passes))  # once the move is over

    def test_cards_come_after_what_they_cite(self):
        codes = ("pass_streak", "recovery_to_shot", "big_save")
        for i, by_id in self.each(lambda i: i["type"] == "card_upgrade" and i["facts"]["reason_code"] in codes):
            self.assertGreaterEqual(i["t_s"], max(by_id[e]["t_s"] for e in i["evidence"]), i["facts"]["reason"])

    def test_big_saves_go_to_the_keeper(self):
        for i, by_id in self.each(lambda i: i["type"] == "card_upgrade" and i["facts"]["reason_code"] == "big_save"):
            shot = by_id[i["evidence"][0]]
            self.assertEqual((roster().players[i["facts"]["player"]].position, shot["outcome"]), ("POR", "saved"))
            self.assertGreaterEqual(shot["xg"], 0.15)

    def test_pass_streaks_are_outfield(self):
        for i, _ in self.each(lambda i: i["type"] == "card_upgrade" and i["facts"]["reason_code"] == "pass_streak"):
            self.assertNotEqual(roster().players[i["facts"]["player"]].position, "POR")
            self.assertEqual(i["facts"]["reason_params"]["count"] % 20, 0)



class DemoMatchesConsistencyTest(unittest.TestCase):
    """What the graphics say about the MVP and the invisible assist agrees with the data."""

    def test_first_place_agrees_everywhere(self):
        from baja_insights.engine.tools import MatchQuery
        for match in ("m001", "f091"):
            insights = load(DATA / match / "insights.json")
            top = next(i for i in insights if i["type"] == "top3")["facts"]["top3"][0]["player"]
            announced = [i["facts"]["player"] for i in insights
                         if i["type"] == "mvp_rank_change" and i["facts"]["to_rank"] == 1]
            tool = MatchQuery.from_files(DATA / match / "events.jsonl").get_mvp_ranking("90:00", 1)
            with self.subTest(match=match):
                self.assertEqual(announced[-1], top)  # a tie never takes first place away
                self.assertEqual(tool["ranking"][0]["player"], top)

    def test_a_run_by_a_player_who_touched_the_ball_is_not_called_invisible(self):
        for match in ("m001", "f091"):
            insights = load(DATA / match / "insights.json")
            chains = [i["facts"]["invisible_assist"] for i in insights
                      if i["type"] == "goal_chain" and i["facts"].get("invisible_assist")]
            top3 = next(i for i in insights if i["type"] == "top3")["facts"]["top3"]
            for row in top3:
                for inv in chains:
                    if inv["player"] == row["player"] and inv["touched_ball"]:
                        with self.subTest(match=match, player=row["player"]):
                            self.assertNotIn("desmarque que abrió un gol sin tocar el balón", row["why"])


if __name__ == "__main__":
    unittest.main()
