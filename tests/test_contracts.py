"""Mocks, generated data and chat tools must all agree with the contracts."""

import helpers  # noqa: F401  (puts src/ on sys.path)
import unittest

from baja_insights.engine.tools import MatchQuery
from helpers import DATA, MOCKS, load, roster, validator


class SchemaTest(unittest.TestCase):
    CASES = [
        ("event", MOCKS / "events_sample.json"),
        ("event", MOCKS / "events_sample.jsonl"),
        ("insight", MOCKS / "insights_sample.json"),
        ("overlay", MOCKS / "overlays_sample.json"),
        ("event", DATA / "m001" / "events.jsonl"),
        ("insight", DATA / "m001" / "insights.json"),
        ("overlay", DATA / "m001" / "overlays.json"),
        ("event", DATA / "free-seed2" / "events.jsonl"),
        ("insight", DATA / "free-seed2" / "insights.json"),
        ("event", DATA / "f091" / "events.jsonl"),
        ("insight", DATA / "f091" / "insights.json"),
        ("overlay", DATA / "f091" / "overlays.json"),
    ]

    def test_all_files_validate(self):
        for schema, path in self.CASES:
            v = validator(schema)
            if v is None:
                self.skipTest("jsonschema not installed")
            with self.subTest(path=path.name):
                errors = [(i, e.message) for i, item in enumerate(load(path)) for e in v.iter_errors(item)]
                self.assertEqual(errors, [])

    def test_json_and_jsonl_mocks_are_identical(self):
        self.assertEqual(load(MOCKS / "events_sample.json"), load(MOCKS / "events_sample.jsonl"))

    def test_overlays_point_to_existing_insights(self):
        insight_ids = {i["insight_id"] for i in load(MOCKS / "insights_sample.json")}
        for o in load(MOCKS / "overlays_sample.json"):
            if o["source_insight"] is not None:
                self.assertIn(o["source_insight"], insight_ids, o["overlay_id"])

    def test_evidence_points_to_mock_events_when_possible(self):
        event_ids = {e["event_id"] for e in load(MOCKS / "events_sample.json")}
        for i in load(MOCKS / "insights_sample.json"):
            if i["type"] in ("goal_chain", "card_upgrade", "duel_state"):
                self.assertTrue(set(i["evidence"]) <= event_ids, i["insight_id"])


class ChatToolsTest(unittest.TestCase):
    """Example results in the mock must have the same keys as the real functions."""

    @classmethod
    def setUpClass(cls):
        cls.spec = load(MOCKS / "chat_tools_sample.json")
        cls.query = MatchQuery(load(DATA / "m001" / "events.jsonl"), roster())

    def test_every_tool_is_implemented(self):
        from baja_insights.engine.tools import TOOL_NAMES
        self.assertEqual(sorted(t["name"] for t in self.spec["tools"]), sorted(TOOL_NAMES))

    def test_example_results_have_the_real_shape(self):
        for conv in self.spec["example_conversations"]:
            for call in conv["tool_calls"]:
                with self.subTest(question=conv["question"], tool=call["name"]):
                    args = dict(call["arguments"])
                    if call["name"] == "get_goal_chain":
                        state = self.query.get_match_state("90:00")
                        args["goal_event_id"] = state["goals"][0]["event_id"]
                    live = self.query.dispatch(call["name"], args)
                    self.assertNotIn("error", live)
                    self.assertEqual(_shape(live), _shape(call["result"]))

    def test_unknown_data_is_reported_not_invented(self):
        self.assertEqual(self.query.dispatch("get_player_summary", {"player": "Messi", "at": "10:00"})["error"],
                         "player_not_found")
        self.assertEqual(self.query.dispatch("get_goal_chain", {"goal_event_id": -1})["error"], "goal_not_found")
        summary = self.query.get_player_summary("Torres", "70:00")
        self.assertIn("distance_km", summary["not_tracked"])
        self.assertEqual(self.query.dispatch("nope", {})["error"], "unknown_tool")


def _shape(value):
    """Keys of dicts (recursively); lists are described by their first element."""
    if isinstance(value, dict):
        return {k: _shape(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_shape(value[0])] if value else []
    return type(value).__name__ if value is not None else None


if __name__ == "__main__":
    unittest.main()
