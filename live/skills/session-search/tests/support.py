"""Load the standalone CLI scripts once, build synthetic session files, and run CLI modes."""
import argparse
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Iterable

SCRIPTS = Path(__file__).parents[1] / "scripts"
SEARCH_SCRIPT = SCRIPTS / "session_search.py"
RECALL_SCRIPT = SCRIPTS / "session_recall.py"
sys.path.insert(0, str(SCRIPTS))

import session_common
import session_search
import session_recall


def header(session_id: str, cwd: Path, version: int = 3) -> dict:
    return {
        "type": "session",
        "version": version,
        "id": session_id,
        "timestamp": "2026-08-01T00:00:00Z",
        "cwd": str(cwd),
    }


def message(entry_id: str, parent_id: str | None, timestamp: str, role: str, content, **extra) -> dict:
    return {
        "type": "message",
        "id": entry_id,
        "parentId": parent_id,
        "timestamp": timestamp,
        "message": {"role": role, "content": content, "timestamp": 0, **extra},
    }


def skill_envelope(name: str, location: str, body: str = "body") -> str:
    return (f'<skill name="{name}" location="{location}">\n'
            f'References are relative to {os.path.dirname(location)}.\n\n'
            f'{body}\n</skill>')


def nested_entry(calls, complete=True):
    return message(
        "result", "call", "2026-09-29T00:00:00Z", "toolResult", [],
        toolCallId="outer", toolName="codemode", isError=False,
        nestedCalls={"calls": calls, "complete": complete},
    )


def cli_argv(mode: str, root: str | Path, cwd: str | Path | None, *extra: str,
             terms: Iterable[str] = ("needle",)) -> list[str]:
    """Arguments for aggregate, find, or recall; a None cwd leaves room for --all-projects."""
    scope = ["--sessions-root", str(root), *(["--cwd", str(cwd)] if cwd is not None else [])]
    if mode == "aggregate":
        return [*scope, *extra]
    return [mode, *scope, *(option for term in terms for option in ("--term", term)),
            *(["--include-evidence"] if mode == "recall" else []), *extra]


def cli_args(mode: str, root: str | Path, cwd: str | Path | None, *extra: str,
             terms: Iterable[str] = ("needle",)) -> argparse.Namespace:
    module = session_search if mode == "aggregate" else session_recall
    return module.build_parser().parse_args(cli_argv(mode, root, cwd, *extra, terms=terms))


def run_mode(mode: str, args: argparse.Namespace, now: datetime) -> dict:
    function = {"aggregate": session_search.aggregate, "find": session_recall.find_output,
                "recall": session_recall.recall_output}[mode]
    return function(args, now)


def write_session(path: Path, head: dict, entries: list[dict], malformed: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(head) + "\n")
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")
        if malformed:
            handle.write("{not-json\n")


@contextmanager
def fixture_tree():
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        root = base / "sessions"
        project_a = base / "project-a"
        project_b = base / "project-b"
        project_a.mkdir()
        project_b.mkdir()

        primary = root / "a" / "primary.jsonl"
        write_session(
            primary,
            header("session-a", project_a),
            [
                message(
                    "a1",
                    None,
                    "2026-08-10T00:00:00Z",
                    "user",
                    skill_envelope("alpha", "/tmp/skills/alpha/SKILL.md", "Investigate failures token=TOPSECRET123456"),
                ),
                message(
                    "a2",
                    "a1",
                    "2026-08-11T00:00:00Z",
                    "assistant",
                    [
                        {"type": "text", "text": "Taking the old branch"},
                        {
                            "type": "toolCall",
                            "id": "tc-read",
                            "name": "read",
                            "arguments": {"path": "/tmp/skills/alpha/SKILL.md", "api_key": "KEY_SHOULD_HIDE_123"},
                        },
                    ],
                    stopReason="toolUse",
                ),
                message(
                    "a3",
                    "a2",
                    "2026-08-12T00:00:00Z",
                    "toolResult",
                    [{"type": "text", "text": "old result"}],
                    toolCallId="tc-read",
                    toolName="read",
                    isError=False,
                ),
                message("b2", "a1", "2026-08-13T00:00:00Z", "assistant", [
                    {"type": "toolCall", "id": "tc-bash", "name": "bash", "arguments": {"command": "false"}}
                ], stopReason="toolUse"),
                message(
                    "b3",
                    "b2",
                    "2026-08-14T00:00:00Z",
                    "toolResult",
                    [{"type": "text", "text": "Repeated FAILURE password=hunter2"}],
                    toolCallId="tc-bash",
                    toolName="bash",
                    isError=True,
                ),
            ],
            malformed=True,
        )
        other = root / "b" / "other.jsonl"
        write_session(
            other,
            header("session-b", project_b),
            [message("c1", None, "2026-08-14T12:00:00Z", "user", "failure in another project")],
        )
        current = root / "a" / "current.jsonl"
        write_session(
            current,
            header("session-current", project_a),
            [message("d1", None, "2026-08-14T13:00:00Z", "user", "current only marker")],
        )
        yield root, project_a, project_b, primary, other, current
