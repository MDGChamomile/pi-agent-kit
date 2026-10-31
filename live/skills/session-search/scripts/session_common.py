"""Storage, scope, time, masking, and output helpers shared by the session CLIs."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable, Iterable, Iterator

MAX_EVIDENCE_CHARS = 300
MAX_WARNING_ITEMS = 100

# Mask before truncation so a secret crossing the truncation boundary cannot leak.
MASK_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"-----BEGIN [^-\n]*PRIVATE KEY-----.*?-----END [^-\n]*PRIVATE KEY-----", re.I | re.S), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+", re.I), r"\1 [REDACTED]"),
    (re.compile(r"(?i)(https?://)([^\s/@:]+):([^\s/@]+)@"), r"\1[REDACTED]@"),
    # Header values can contain several cookies and folded continuation lines.
    (re.compile(r"(?im)(?<![\w-])((?:set-cookie|cookie)[ \t]*:[ \t]*)[^\r\n]*(?:\r?\n[ \t]+[^\r\n]*)*"), r"\1[REDACTED]"),
    # Quoted values may contain whitespace, separators, and escaped quotes.
    # An unterminated quoted value is masked through the end of the input.
    (re.compile(
        r'''(["']?(?:api[_-]?key|access[_-]?token|auth(?:orization)?|(?:set-)?cookie|password|passwd|secret|token)["']?\s*[:=]\s*)'''
        r'''(?:"(?:\\.|[^"\\])*(?:"|\\?$)|'(?:\\.|[^'\\])*(?:'|\\?$)|[^"'\s,;}]+)''',
        re.I | re.S,
    ), r"\1[REDACTED]"),
    (re.compile(r"(?i)([?&](?:api[_-]?key|access[_-]?token|auth|password|secret|token)=)[^&#\s]+"), r"\1[REDACTED]"),
    (re.compile(r"\b(?:sk|pk)-[A-Za-z0-9_-]{12,}\b"), "[REDACTED_KEY]"),
)


def pi_environment_path(value: str) -> Path:
    """Expand only Pi's own-home tilde forms, never another user's home."""
    if value == "~":
        return Path.home()
    if value.startswith("~/") or (os.name == "nt" and value.startswith("~\\")):
        return Path.home() / value[2:]
    # Prevent later generic expanduser calls from expanding a literal ~user.
    return Path(value).absolute()


def default_sessions_root() -> Path:
    """Resolve Pi's storage overrides when building a CLI, not at import time."""
    if value := os.environ.get("PI_CODING_AGENT_SESSION_DIR"):
        return pi_environment_path(value)
    agent_dir = os.environ.get("PI_CODING_AGENT_DIR")
    return (pi_environment_path(agent_dir) if agent_dir else Path.home() / ".pi" / "agent") / "sessions"


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def normalized_path(value: str | Path) -> str:
    return str(Path(value).expanduser().resolve(strict=False))


def mask_secrets(value: str) -> str:
    for pattern, replacement in MASK_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def mask_and_shorten(
    value: str, limit: int = MAX_EVIDENCE_CHARS, queries: Iterable[str] = (),
) -> str:
    return mask_and_shorten_with_metadata(value, limit, queries)[0]


def mask_and_shorten_with_metadata(
    value: str, limit: int = MAX_EVIDENCE_CHARS, queries: Iterable[str] = (),
) -> tuple[str, bool]:
    """Return masked evidence and whether normalized masked text was shortened."""
    masked = re.sub(r"\s+", " ", mask_secrets(value)).strip()
    if limit <= 0:
        return "", bool(masked)
    if len(masked) <= limit:
        return masked, False

    folded = masked.casefold()
    positions = []
    for query in queries:
        query = re.sub(r"\s+", " ", query).strip().casefold()
        if query:
            position = folded.find(query)
            if position >= 0:
                positions.append(position)
    if positions and limit >= 3:
        # casefold can expand characters (e.g. ß -> ss); translate the offset
        # back to masked text without ever consulting the unmasked source.
        target = min(positions)
        folded_offset = 0
        for index, char in enumerate(masked):
            folded_offset += len(char.casefold())
            if folded_offset > target:
                break
        budget = limit - 2  # Reserve both possible omission markers.
        start = min(max(0, index - budget // 2), len(masked) - budget)
        end = start + budget
        return ("…" if start else "") + masked[start:end] + ("…" if end < len(masked) else ""), True
    return masked[: limit - 1] + "…", True


def text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    )


class WarningCollector:
    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._items: list[dict[str, str]] = []
        self._seen: set[tuple[str, str]] = set()

    def add(self, path: Path, kind: str) -> None:
        path_text = str(path)
        key = (path_text, kind)
        if key in self._seen:
            return
        self._seen.add(key)
        self._counts[kind] += 1
        if len(self._items) < MAX_WARNING_ITEMS:
            self._items.append({"path": path_text, "kind": kind})

    @property
    def count(self) -> int:
        return len(self._seen)

    def output(self, include_items: bool) -> dict[str, Any]:
        result: dict[str, Any] = {
            "count": self.count,
            "by_kind": dict(sorted(self._counts.items())),
        }
        if include_items:
            result["items"] = list(self._items)
            result["truncated"] = self.count > len(self._items)
        return result


def read_session_header(handle: BinaryIO) -> dict[str, Any] | None:
    """Decode only the header; callers retain their own scope and warning policy."""
    text = handle.readline().decode("utf-8")
    try:
        header = json.loads(text)
    except (ValueError, TypeError, RecursionError):
        return None
    return header if isinstance(header, dict) and header.get("type") == "session" else None


def read_session_entries(
    handle: BinaryIO, path: Path, warnings: WarningCollector,
) -> Iterator[dict[str, Any]]:
    """Skip malformed JSON entries; leave I/O and decoding failures to callers."""
    for line in handle:
        text = line.decode("utf-8")
        try:
            entry = json.loads(text)
        except (ValueError, TypeError, RecursionError):
            warnings.add(path, "invalid_json_line")
            continue
        if not isinstance(entry, dict):
            warnings.add(path, "invalid_entry")
            continue
        yield entry


def session_version(header: dict[str, Any], path: Path, warnings: WarningCollector) -> int | None:
    value = header.get("version")
    if value is None:
        warnings.add(path, "missing_session_version")
        return 1
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        warnings.add(path, "invalid_session_version")
        return None
    if value > 3:
        warnings.add(path, "unsupported_session_version")
        return None
    return value


class InvalidArgumentError(Exception):
    pass


class SessionArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InvalidArgumentError(message)


def add_storage_scope_arguments(parser: argparse.ArgumentParser) -> None:
    """Share storage/project selection without coupling search pipelines."""
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--all-projects", action="store_true", help="search sessions from every project")
    scope.add_argument("--cwd", default=os.getcwd(), help="project cwd to match exactly (default: current cwd)")
    parser.add_argument("--include-current", action="store_true", help="include PI_SESSION_FILE (excluded by default)")
    parser.add_argument(
        "--additional-sessions-root", type=Path, action="append", default=[], metavar="PATH",
        help="also search this directory recursively; repeat for multiple directories; "
             "additive to the selected sessions root; all directories must be readable",
    )
    parser.add_argument(
        "--sessions-root", type=Path, default=default_sessions_root(), metavar="PATH",
        help="replace the primary sessions directory; default precedence: PI_CODING_AGENT_SESSION_DIR, "
             "PI_CODING_AGENT_DIR/sessions, ~/.pi/agent/sessions",
    )


def add_exclusion_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--exclude-session-file", action="append", default=[], metavar="PATH",
                        help="exclude an exact session file before opening; repeatable; paths resolve from process cwd; "
                             "overrides --include-current; reports path-free requested/excluded/unmatched counts")


def normalized_exclusions(values: Iterable[str]) -> frozenset[str]:
    paths: set[str] = set()
    for value in values:
        # Validate before Path('') can silently become the current directory.
        if not value or "\x00" in value:
            raise ValueError("session exclusion is invalid")
        try:
            paths.add(normalized_path(value))
        except (ValueError, OSError, RuntimeError) as error:
            raise ValueError("session exclusion is invalid") from error
    return frozenset(paths)


def exclusion_summary(exclusions: frozenset[str], matched: set[str], excluded_count: int) -> dict[str, int]:
    # A current-session overlap is matched, but counted only in the automatic counter.
    return {
        "session_file_exclusions_requested": len(exclusions),
        "explicit_session_files_excluded": excluded_count,
        "session_file_exclusions_unmatched": len(exclusions - matched),
    }


class SessionFileExclusions:
    """Count pre-read exclusions using each caller's normalized file identity."""

    def __init__(self, exclusions: frozenset[str], include_current: bool) -> None:
        self.exclusions = exclusions
        self.include_current = include_current
        self.current = normalized_path(os.environ["PI_SESSION_FILE"]) if os.environ.get("PI_SESSION_FILE") else None
        self.matched: set[str] = set()
        self.excluded_current = 0
        self.excluded_explicit = 0

    def excludes(self, path_key: str) -> bool:
        if path_key in self.exclusions:
            self.matched.add(path_key)
        if not self.include_current and self.current and path_key == self.current:
            self.excluded_current += 1
            return True
        if path_key in self.exclusions:
            self.excluded_explicit += 1
            return True
        return False

    def summary(self) -> dict[str, int]:
        return {
            "current_session_files_excluded": self.excluded_current,
            **exclusion_summary(self.exclusions, self.matched, self.excluded_explicit),
        }


def discover_session_files(
    roots: Iterable[Path], on_outside: Callable[[Path], None] | None = None,
) -> list[Path]:
    """Fail visibly on traversal errors; keep only files under an allowed root."""
    paths: dict[str, Path] = {}
    allowed_roots: dict[str, Path] = {}
    for value in roots:
        root = value.expanduser()
        key = normalized_path(root)
        if not root.is_dir():
            raise RuntimeError("session root is unavailable")
        allowed_roots.setdefault(key, root)

    def traversal_error(error: OSError) -> None:
        raise error

    for root in allowed_roots.values():
        # Unlike Path.rglob, walk's onerror makes inaccessible subtrees visible.
        # Do not follow nested directory symlinks.
        for directory, _dirs, files in os.walk(root, onerror=traversal_error):
            for name in files:
                if name.endswith(".jsonl"):
                    path = Path(directory) / name
                    resolved = Path(normalized_path(path))
                    if not any(resolved.is_relative_to(allowed) for allowed in allowed_roots):
                        if on_outside is not None:
                            on_outside(path)
                        continue
                    paths.setdefault(str(resolved), path)
    return sorted(paths.values())


def cutoff_for_days(
    days: float | None, now: datetime | None = None
) -> datetime | None:
    if days is None:
        return None
    if not math.isfinite(days) or days < 0:
        raise ValueError("--days must be a finite non-negative number")
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    try:
        return current_time.astimezone(timezone.utc) - timedelta(days=days)
    except OverflowError as error:
        raise ValueError("--days exceeds the supported date range") from error


def add_time_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--days", type=float, help="include entries/messages from the last N days")
    parser.add_argument("--since", metavar="TIMESTAMP",
                        help="inclusive start: YYYY-MM-DDTHH:MM:SS[.ffffff]Z or ±HH:MM offset; not with --days")
    parser.add_argument("--until", metavar="TIMESTAMP",
                        help="exclusive end: same timezone-required format as --since; not with --days")


def parse_time_boundary(value: str) -> datetime:
    # Keep CLI validation separate from the permissive historical-record parser.
    match = re.fullmatch(
        r"([0-9]{4}-[0-9]{2}-[0-9]{2}T(?:[01][0-9]|2[0-3]):[0-9]{2}:[0-9]{2})"
        r"(?:\.([0-9]{1,6}))?(Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])", value,
    )
    if match is None:
        raise ValueError("time boundary is invalid")
    # Python 3.10 fromisoformat accepts only 3 or 6 fractional digits.
    seconds, fraction, offset = match.groups()
    parsed = parse_timestamp(f"{seconds}.{(fraction or '').ljust(6, '0')}{offset}")
    if parsed is None:
        raise ValueError("time boundary is invalid")
    return parsed


@dataclass(frozen=True)
class TimeRange:
    since: datetime | None = None
    until: datetime | None = None

    def contains(self, timestamp: datetime | None) -> bool:
        if self.since is None and self.until is None:
            return True
        return (timestamp is not None
                and (self.since is None or timestamp >= self.since)
                and (self.until is None or timestamp < self.until))

    def view(self) -> dict[str, str | None]:
        return {name: value.isoformat().replace("+00:00", "Z") if value is not None else None
                for name, value in (("since", self.since), ("until", self.until))}


def time_range_for_args(args: argparse.Namespace, now: datetime | None = None) -> TimeRange:
    if args.days is not None and (args.since is not None or args.until is not None):
        raise ValueError("relative and absolute time bounds cannot be combined")
    since = parse_time_boundary(args.since) if args.since is not None else cutoff_for_days(args.days, now)
    until = parse_time_boundary(args.until) if args.until is not None else None
    if since is not None and until is not None and since >= until:
        raise ValueError("time range is empty or reversed")
    return TimeRange(since, until)


def emit_json(value: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    # JSON accepts lone surrogates, but UTF-8 cannot encode them. Keep ordinary
    # Unicode readable while emitting these code points as valid JSON escapes.
    print(serialized.encode("utf-8", "backslashreplace").decode("utf-8"))


def emit_error(code: str, message: str) -> int:
    output = {
        "status": "error",
        "error": {"code": code, "message": message},
        "results": [],
    }
    emit_json(output)
    return 2
