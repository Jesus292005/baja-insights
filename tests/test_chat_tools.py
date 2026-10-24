"""Chat functions with the inputs a model or a fan may send: bad times, empty names, no accents."""

import helpers  # noqa: F401  (puts src/ on sys.path)
import unittest

from baja_insights.contract import parse_clock
from baja_insights.engine.tools import MatchQuery
from helpers import DATA, load, roster


class ParseClockTest(unittest.TestCase):
    def test_valid_times(self):
        for value, seconds in (("63:09", 3789), ("63", 3780), (3789, 3789), ("3789s", 3789), ("00:00", 0),
                               ("90:00", 5400), (" 45 ", 2700), (12.9, 12)):
            self.assertEqual(parse_clock(value), seconds, value)

    def test_invalid_times_raise(self):
        for value in ("99:99", "10:60", "-1", "-0:30", "10:-5", -5, "abc", "", True, None):
            with self.assertRaises((ValueError, TypeError), msg=repr(value)):
                parse_clock(value)


class ChatToolsInputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.query = MatchQuery(load(DATA / "m001" / "events.jsonl"), roster())

    def ask(self, name, **arguments):
        return self.query.dispatch(name, arguments)

    def test_bad_times_are_bad_arguments(self):
        for at in ("99:99", "-1", "10:75", None, "mañana"):
            self.assertEqual(self.ask("get_match_state", at=at).get("error"), "bad_arguments", at)

    def test_after_the_final_whistle_is_the_final_state(self):
        late = self.ask("get_match_state", at="92:30")
        self.assertEqual((late["at"], late["at_s"]), ("90:00", 5400))
        self.assertEqual(late["scoreline"], self.ask("get_match_state", at="90:00")["scoreline"])

    def test_missing_names_are_not_found_never_a_crash_or_a_guess(self):
        for player in (None, "", "   ", 7):
            self.assertEqual(self.ask("get_player_summary", player=player, at="70:00").get("error"),
                             "player_not_found", repr(player))
        for team in ("", "a", "fc", None):
            self.assertEqual(self.ask("get_team_phase", team=team, **{"from": "00:00", "to": "10:00"}).get("error"),
                             "team_not_found", repr(team))

    def test_names_without_accents_or_capitals(self):
        self.assertEqual(self.ask("get_player_summary", player="ramirez", at="70:00")["player"], "M. Ramírez")
        self.assertEqual(self.ask("get_player_summary", player="  TORRES ", at="70:00")["player"], "J. Torres")
        self.assertEqual(self.ask("get_team_phase", team="bahia", **{"from": "00:00", "to": "10:00"})["team"], "Bahía FC")
        self.assertEqual(self.ask("get_team_phase", team="cardon", **{"from": "00:00", "to": "10:00"})["team"], "Real Cardón")
        self.assertEqual(roster().find_team("CAR"), "Real Cardón")


if __name__ == "__main__":
    unittest.main()
