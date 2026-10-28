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

    def test_the_unscripted_demo_is_up_to_date(self):
        """data/f091 is the match without a script that the team shows: regenerate it (and its graphics
        orders) whenever the generator changes."""
        self.assertEqual(generate_match(roster(), seed=91, script=None, match_id="f091"),
                         load(DATA / "f091" / "events.jsonl"))

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

    def test_a_pressed_player_often_lets_it_go_and_holding_it_is_a_risk(self):
        released = released_ok = held = held_lost = 0
        for events in self.matches:
            play = [e for e in events if e.get("team") and e.get("start")]
            for i, e in enumerate(play[:-1]):
                if e["type"] != "pressure":
                    continue
                a = play[i + 1]
                if a["type"] == "pass" and a["player"] == e["target"] and a["t_s"] - e["t_s"] <= 1:
                    released += 1
                    released_ok += a["outcome"] == "complete"
                    continue
                held += 1
                for b in play[i + 1:i + 5]:
                    if b["team"] == e["team"] and b["type"] in ("tackle", "recovery", "duel") \
                            and (b["type"] != "tackle" or b["outcome"] == "won"):
                        held_lost += 1
                        break
                    if b["type"] == "pass" and b["team"] != e["team"]:
                        held_lost += b["outcome"] == "incomplete"
                        break
        self.assertTrue(0.35 <= released / (released + held) <= 0.8, (released, held))
        self.assertGreaterEqual(released_ok / released, 0.75)
        self.assertGreaterEqual(held_lost / held, 0.35)  # waiting for the presser loses the ball a lot

    def test_strikers_shoot_first_time(self):
        """Most shots in open play come within 2 seconds of receiving the ball."""
        quick = total = 0
        for events in self.matches:
            play = [e for e in events if e.get("team") and e.get("start")]
            for i, e in enumerate(play):
                if e["type"] != "shot" or e.get("set_piece"):
                    continue
                prev = next((p for p in reversed(play[:i]) if p["type"] == "pass" and p["team"] == e["team"]), None)
                if prev and prev["outcome"] == "complete" and prev.get("receiver") == e["player"] and not prev.get("cross"):
                    total += 1
                    quick += e["t_s"] - prev["t_s"] <= 2
        self.assertGreaterEqual(quick / total, 0.5)

    def test_crosses_are_hard_to_complete(self):
        crosses = [e for events in self.matches for e in events if e["type"] == "pass" and e.get("cross")
                   and not e.get("set_piece")]
        self.assertTrue(0.15 <= sum(e["outcome"] == "complete" for e in crosses) / len(crosses) <= 0.4)

    def test_there_are_counter_attacks(self):
        """Some balls won in the own half end in a shot within 15 seconds."""
        won = broke = 0
        for events in self.matches:
            by_possession = {}
            for e in events:
                if e.get("team") and e.get("start"):
                    by_possession.setdefault(e["possession_id"], []).append(e)
            for chain in by_possession.values():
                first = chain[0]
                if first["type"] == "recovery" and prog(first) < 52.5:
                    won += 1
                    broke += any(x["type"] == "shot" and x["team"] == first["team"] and x["t_s"] - first["t_s"] <= 15
                                 for x in chain)
        self.assertGreaterEqual(broke / won, 0.015)

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
