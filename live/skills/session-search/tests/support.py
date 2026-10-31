"""Load the standalone CLI scripts once, build synthetic session files, and run CLI modes."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
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
