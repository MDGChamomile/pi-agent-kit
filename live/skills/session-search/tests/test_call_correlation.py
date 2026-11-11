"""Skill outcomes belong to the matching call on their recorded ancestry."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from support import cli_args, header, message, session_search, skill_envelope, write_session

STAMP = "2026-08-14T00:00:00Z"


def call(entry_id, parent, path, *, tool="read", timestamp=STAMP):
    return message(entry_id, parent, timestamp, "assistant", [
        {"type": "toolCall", "id": "shared", "name": tool, "arguments": {"path": path}},
    ])


def result(entry_id, parent, *, error=False, tool="read", timestamp=STAMP):
    return message(entry_id, parent, timestamp, "toolResult", "synthetic result",
                   toolName=tool, toolCallId="shared", isError=error)


class CallCorrelationTests(unittest.TestCase):
    def aggregate(self, entries, version=3, flags=()):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_session(root / "record.jsonl", {**header("synthetic", root), "version": version}, entries)
            return session_search.aggregate(cli_args("aggregate", root, root, *flags))

    def test_each_call_is_interpreted_once_for_events_and_result_correlation(self):
        first = call("a", None, "/alpha/SKILL.md")
        first["message"]["content"].extend([
            {"type": "toolCall", "id": "shared", "name": "read", "arguments": {"path": "/beta/SKILL.md"}},
            {"type": "toolCall", "name": "read", "arguments": {"path": "/gamma/SKILL.md"}},
        ])
        for version in (1, 3):
            with self.subTest(version=version), patch.object(
                session_search, "skill_read_name", wraps=session_search.skill_read_name,
            ) as classify:
                summary = self.aggregate([first, result("ar", "a")], version)["summary"]
            self.assertEqual(classify.call_count, 3)
            self.assertEqual(summary["skill_file_read_attempts"], {"alpha": 1, "beta": 1, "gamma": 1})
            self.assertEqual(summary["skill_file_read_successes"], {"beta": 1})

    def test_non_skill_call_shadows_a_reused_skill_call_id(self):
        for version in (1, 2, 3):
            for tool, path in (("read", "/project/README.md"), ("bash", "/alpha/SKILL.md")):
                with self.subTest(version=version, tool=tool):
                    summary = self.aggregate([
                        call("a", None, "/alpha/SKILL.md"), result("ar", "a"),
                        call("b", "ar", path, tool=tool), result("br", "b", tool=tool),
                    ], version)["summary"]
                    self.assertEqual(summary["skill_file_read_attempts"], {"alpha": 1})
                    self.assertEqual(summary["skill_file_read_successes"], {"alpha": 1})

    def test_sibling_calls_are_resolved_by_parent_not_file_order(self):
        entries = [
            call("a", None, "/alpha/SKILL.md"), call("b", None, "/beta/SKILL.md"),
            result("ar", "a"), result("br", "b", error=True),
        ]
        for version in (1, 2, 3):
            for evidence in (False, True):
                with self.subTest(version=version, evidence=evidence):
                    output = self.aggregate(entries, version, ["--include-evidence"] if evidence else [])
                    summary = output["summary"]
                    self.assertEqual(summary["skill_file_read_attempts"], {"alpha": 1, "beta": 1})
                    self.assertEqual(summary["skill_file_read_successes"], {"beta" if version == 1 else "alpha": 1})
                    self.assertEqual(summary["skill_file_read_errors"], {"beta": 1})
                    if evidence and version >= 2:
                        outcomes = {item["entry_id"]: item for item in output["results"]}
                        self.assertFalse(outcomes["ar"]["on_latest_leaf"])
                        self.assertTrue(outcomes["br"]["on_latest_leaf"])

    def test_nearest_matching_call_wins_and_batch_filters_keep_the_same_counts(self):
        entries = [
            call("a", None, "/alpha/SKILL.md"), result("ar", "a"),
            call("b", "ar", "/beta/SKILL.md"), result("br", "b"),
        ]
        for version in (1, 2, 3):
            with self.subTest(version=version):
                filters = [{"skill": ["alpha"]}, {"skill": ["beta"]}]
                batch = self.aggregate(entries, version, [
                    flag for item in filters for flag in ("--batch-filter", json.dumps(item))
                ])
                for item, skill in zip(batch["batches"], ("alpha", "beta")):
                    single = self.aggregate(entries, version, ["--skill", skill])
                    for key in ("skill_file_read_attempts", "skill_file_read_successes"):
                        self.assertEqual(item["summary"][key], {skill: 1})
                        self.assertEqual(item["summary"][key], single["summary"][key])

    def test_missing_or_cyclic_result_ancestry_does_not_borrow_a_sibling_call(self):
        for version in (2, 3):
            for parent in (None, "missing", "result", []):
                with self.subTest(version=version, parent=parent):
                    summary = self.aggregate([
                        call("a", None, "/alpha/SKILL.md"), result("result", parent),
                    ], version)["summary"]
                    self.assertEqual(summary["skill_file_read_attempts"], {"alpha": 1})
                    self.assertEqual(summary["skill_file_read_successes"], {})

    def test_call_history_is_kept_before_time_and_event_filters(self):
        for version in (2, 3):
            with self.subTest(version=version):
                summary = self.aggregate([
                    call("a", None, "/alpha/SKILL.md", timestamp="2026-08-01T00:00:00Z"),
                    call("b", None, "/beta/SKILL.md", timestamp="2026-08-01T00:00:00Z"),
                    result("ar", "a"),
                ], version, ["--since", "2026-08-14T00:00:00Z", "--role", "toolresult"])["summary"]
                self.assertEqual(summary["skill_file_read_attempts"], {})
                self.assertEqual(summary["skill_file_read_successes"], {"alpha": 1})

    def test_unknown_call_id_does_not_walk_unrelated_history(self):
        class UnreadHistory(dict):
            def get(self, key, default=None):
                raise AssertionError("An unknown call ID must not traverse the history")

        self.assertEqual(session_search.skill_read_calls_for_result(
            result("ar", "a"), {"other-id": {"a": "alpha"}}, UnreadHistory(),
        ), {})

    def test_result_keeps_the_identity_recorded_at_its_call(self):
        for version in (1, 2, 3):
            with self.subTest(version=version):
                summary = self.aggregate([
                    message("name-a", None, STAMP, "user", skill_envelope("original", "/folder/SKILL.md")),
                    call("a", "name-a", "/folder/SKILL.md"),
                    message("name-b", "a", STAMP, "user", skill_envelope("renamed", "/folder/SKILL.md")),
                    result("ar", "name-b"),
                ], version)["summary"]
                self.assertEqual(summary["skill_file_read_successes"], {"original": 1})
