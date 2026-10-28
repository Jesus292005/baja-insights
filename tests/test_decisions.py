"""Free matches: decisions come from the play, fouls in the box are penalties and the score never
changes the finishing. The demo match m001 keeps the scripted generator untouched."""

import helpers  # noqa: F401  (puts src/ on sys.path)
import math
import statistics
import unittest

from baja_insights.generator import DEMO_SEED, generate_match
from baja_insights.generator.decisions import PENALTY_SPOT_PROG, in_box
from baja_insights.generator.xg import expected_goals
from helpers import DATA, load, roster, validator


def prog(e):
    return e["start"][0] if e["team"] == roster().home else 105 - e["start"][0]


class DecisionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matches = [generate_match(roster(), seed=s, script=None) for s in range(1, 61)]

    def test_the_scripted_demo_is_untouched(self):
        self.assertEqual(generate_match(roster(), seed=DEMO_SEED, script="m001"), load(DATA / "m001" / "events.jsonl"))

    def test_free_matches_follow_the_contract(self):
        v = validator("event")
        if v is None:
            self.skipTest("jsonschema not installed")
        for events in self.matches[:10]:
            self.assertEqual([err.message for e in events for err in v.iter_errors(e)], [])

    def test_a_free_player_with_a_big_chance_shoots(self):
        """Unpressed, with a chance of 0.35 xG or more, a player shoots instead of passing back."""
        big = []
        for events in self.matches:
            for e in events:
                if e["type"] not in ("pass", "shot") or e.get("set_piece") or e["under_pressure"]:
                    continue
                chance = e["xg"] if e["type"] == "shot" else expected_goals(prog(e), e["start"][1], False, False)
                if chance >= 0.35:
                    big.append(e["type"] == "shot")
        self.assertGreaterEqual(len(big), 5)
        self.assertGreaterEqual(sum(big) / len(big), 0.85)

    def test_passes_in_the_box_do_not_all_go_backwards(self):
        back = total = 0
        for events in self.matches:
            for e in events:
                if e["type"] == "pass" and not e.get("set_piece") and in_box(prog(e), e["start"][1]):
                    end = e["end"][0] if e["team"] == roster().home else 105 - e["end"][0]
                    total += 1
                    back += end < prog(e) - 3
        self.assertLessEqual(back / total, 0.6)

    def test_a_foul_in_the_box_is_a_penalty(self):
        fouls = penalties = 0
        for events in self.matches:
            play = [e for e in events if e.get("team") and e.get("start")]
            for a, b in zip(play, play[1:]):
                if a["type"] != "foul":
                    continue
                fouled_team = roster().players[a["fouled"]].team
                p = a["start"][0] if fouled_team == roster().home else 105 - a["start"][0]
                if not in_box(p, a["start"][1]):
                    continue
                fouls += 1
                with self.subTest(foul=a["event_id"]):
                    self.assertEqual((b["type"], b.get("set_piece"), b["team"], b["xg"]),
                                     ("shot", "penalty", fouled_team, 0.76))
                    self.assertEqual((prog(b), b["start"][1]), (PENALTY_SPOT_PROG, 34.0))
            penalties += sum(e.get("set_piece") == "penalty" for e in events)
        self.assertEqual(fouls, penalties)
        self.assertTrue(0.1 <= penalties / len(self.matches) <= 0.5, penalties)  # about 0.3 in the Premier League

    def test_the_score_never_changes_the_finishing(self):
        """Goals follow the xG of the shots, whoever is ahead."""
        xg = goals = 0.0
        for events in self.matches:
            xg += sum(e["xg"] for e in events if e["type"] == "shot")
            goals += sum(e["type"] == "goal" for e in events)
        self.assertTrue(0.85 <= goals / xg <= 1.15, (goals, xg))


class ScoreDistributionTest(unittest.TestCase):
    def test_scores_look_like_the_premier_league(self):
        totals = []
        for s in range(1, 201):
            final = generate_match(roster(), seed=s, script=None)[-1]["scoreline"]
            totals.append(final["home"] + final["away"])
        self.assertTrue(2.3 <= statistics.fmean(totals) <= 3.4)
        self.assertTrue(0.02 <= sum(t == 0 for t in totals) / len(totals) <= 0.15)  # 0-0: about 7%
        self.assertLessEqual(sum(t >= 8 for t in totals) / len(totals), 0.02)
        self.assertLessEqual(max(totals), 10)


if __name__ == "__main__":
    unittest.main()
