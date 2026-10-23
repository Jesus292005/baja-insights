import helpers  # noqa: F401  (puts src/ on sys.path)
import unittest

from baja_insights.contract import fmt_clock, parse_clock
from baja_insights.engine.scoring import (
    duel_bar, mvp_score, pass_difficulty, priority_duel, priority_milestone, priority_mvp,
    split_credit, vs_role,
)
from baja_insights.roster import overall

HOME = "Bahía FC"


class ClockTest(unittest.TestCase):
    def test_round_trip(self):
        self.assertEqual(parse_clock("63:09"), 3789)
        self.assertEqual(fmt_clock(3789), "63:09")
        self.assertEqual(parse_clock("35"), 2100)
        self.assertEqual(parse_clock(3789), 3789)
        self.assertEqual(parse_clock("3789"), 3789)


class PassDifficultyTest(unittest.TestCase):
    def test_salgado_line_breaking_pass(self):
        event = {"type": "pass", "team": HOME, "start": [70, 30], "end": [96, 40],
                 "under_pressure": True, "lines_broken": 2}
        self.assertEqual(pass_difficulty(event, HOME), 0.88)

    def test_backwards_pass_is_easy(self):
        event = {"type": "pass", "team": HOME, "start": [52.5, 34], "end": [45, 36],
                 "under_pressure": False, "lines_broken": 0}
        self.assertLess(pass_difficulty(event, HOME), 0.1)

    def test_direction_depends_on_team(self):
        away = {"type": "pass", "team": "Real Cardón", "start": [50, 45], "end": [28, 58],
                "under_pressure": True, "lines_broken": 2}
        self.assertGreater(pass_difficulty(away, HOME), 0.8)


class RoleAndMvpTest(unittest.TestCase):
    BASE = {"duels_won": 4.5, "recoveries": 2.5, "progressive_passes": 2.5, "key_passes": 1.6}

    def test_exactly_expected_is_zero(self):
        actual = {k: v for k, v in self.BASE.items()}
        self.assertEqual(vs_role(actual, self.BASE, 90), 0.0)

    def test_clipped_range(self):
        huge = {k: 50 for k in self.BASE}
        self.assertEqual(vs_role(huge, self.BASE, 90), 1.0)
        self.assertEqual(vs_role({}, self.BASE, 90), -1.0)

    def test_mvp_is_monotonic_and_bounded(self):
        scores = [mvp_score(p, 0.0, 90) for p in (0, 1, 3, 6, 12, 40)]
        self.assertEqual(scores, sorted(scores))
        self.assertTrue(all(0 <= s <= 10 for s in scores))


class DuelAndPriorityTest(unittest.TestCase):
    def test_bar(self):
        self.assertEqual(duel_bar(-0.4, 0.6), -0.5)
        self.assertEqual(duel_bar(0.3, 0.1), 0.1)
        self.assertEqual(duel_bar(1, -1), 1.0)

    def test_priorities_match_mocks(self):
        self.assertEqual(priority_mvp(7, 3), 0.61)
        self.assertEqual(priority_mvp(3, 1), 0.83)
        self.assertEqual(priority_duel(-0.5, False), 0.45)
        self.assertEqual(priority_duel(0.1, True), 0.52)
        self.assertEqual(priority_milestone(0.55), 0.75)


class CreditTest(unittest.TestCase):
    def test_sums_to_one(self):
        for weights in ([2.0, 2.85, 4.0, 2.5], [1, 1, 1], [3, 0.1], [2.0, 3.0, 2.5, 2.5]):
            self.assertAlmostEqual(sum(split_credit(weights)), 1.0, places=9)

    def test_equalizer_credit(self):
        self.assertEqual(split_credit([2.0, 2.85, 4.0, 2.5]), [0.18, 0.25, 0.35, 0.22])


class OverallTest(unittest.TestCase):
    def test_overall_is_rounded_mean(self):
        torres = {"ritmo": 84, "disparo": 68, "vision": 66, "regate": 78, "defensa": 58, "fisico": 66, "sin_balon": 68}
        self.assertEqual(overall(torres), 70)


if __name__ == "__main__":
    unittest.main()
