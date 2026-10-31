"""Load the standalone CLI scripts once and build synthetic session files."""
import json
from pathlib import Path
import sys

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


def write_session(path: Path, head: dict, entries: list[dict], malformed: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(head) + "\n")
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")
        if malformed:
            handle.write("{not-json\n")
