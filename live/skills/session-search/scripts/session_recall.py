#!/usr/bin/env python3
"""Find and recall bounded evidence from active branches of local Pi sessions."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import session_search

DEFAULT_CANDIDATE_LIMIT = 10
MAX_CANDIDATE_LIMIT = 50
MAX_TERMS = 8
MAX_TERM_CHARS = 100
MIN_TERM_CHARS = 2
MAX_WINDOWS = 3
MAX_MESSAGES_PER_WINDOW = 5
MAX_MESSAGE_CHARS = 300
MAX_TOTAL_EVIDENCE_CHARS = 6000


@dataclass(frozen=True)
class RecallMessage:
    entry_id: str | None
    timestamp: str | None
    role: str
    text: str


@dataclass(frozen=True)
class Candidate:
    path: Path
    matching_messages: int
    matched_terms: int
    latest_match: datetime
    message_fingerprint: str

class CandidateNotFoundError(Exception):
    pass


def normalize_terms(values: Iterable[str]) -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = " ".join(value.split()).casefold()
        if len(normalized) < MIN_TERM_CHARS or len(normalized) > MAX_TERM_CHARS:
            raise ValueError("recall terms have invalid lengths")
        if normalized not in seen:
            seen.add(normalized)
            terms.append(normalized)
    if not terms or len(terms) > MAX_TERMS:
        raise ValueError("recall requires a bounded number of terms")
    return tuple(terms)


def active_entry_ids(entries: list[dict[str, Any]], version: int) -> list[str] | None:
    if version == 1:
        return [entry["id"] for entry in entries if isinstance(entry.get("id"), str)]

    parent_by_id: dict[str, str | None] = {}
    leaf_id: str | None = None
    for entry in entries:
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or entry_id in parent_by_id:
            return None
        parent_id = entry.get("parentId")
        if parent_id is not None and not isinstance(parent_id, str):
            return None
        parent_by_id[entry_id] = parent_id
        leaf_id = entry_id

    if leaf_id is None:
        return []
    path: list[str] = []
    seen: set[str] = set()
    current: str | None = leaf_id
    while current is not None:
        if current in seen or current not in parent_by_id:
            return None
        seen.add(current)
        path.append(current)
        current = parent_by_id[current]
    path.reverse()
    return path


def recall_text(entry: dict[str, Any]) -> RecallMessage | None:
    if entry.get("type") != "message" or not isinstance(entry.get("message"), dict):
        return None
    message = entry["message"]
    role = message.get("role")
    if role not in {"user", "assistant"}:
        return None
    # text_content deliberately ignores thinking and tool-call blocks.
    text = session_search.text_content(message.get("content"))
    if not text:
        return None
    entry_id = entry.get("id")
    parsed_timestamp = session_search.parse_timestamp(entry.get("timestamp"))
    timestamp = (
        parsed_timestamp.isoformat().replace("+00:00", "Z")
        if parsed_timestamp is not None
        else None
    )
    return RecallMessage(
        entry_id=entry_id if isinstance(entry_id, str) else None,
        timestamp=timestamp,
        role=role,
        text=text,
    )


def read_active_messages(
    path: Path,
    target_cwd: str,
    all_projects: bool,
    warnings: session_search.WarningCollector,
) -> tuple[list[RecallMessage], int] | None:
    scope_confirmed = False
    try:
        with path.open("r", encoding="utf-8") as handle:
            try:
                header = json.loads(handle.readline())
            except (json.JSONDecodeError, TypeError):
                if all_projects:
                    warnings.add(path, "invalid_header")
                return None
            if not isinstance(header, dict) or header.get("type") != "session":
                if all_projects:
                    warnings.add(path, "invalid_header")
                return None
            header_cwd = header.get("cwd")
            if not all_projects and (
                not isinstance(header_cwd, str)
                or session_search.normalized_path(header_cwd) != target_cwd
            ):
                return ([], -1)
            scope_confirmed = True
            version = session_search.session_version(header, path, warnings)
            if version is None:
                return None

            entries: list[dict[str, Any]] = []
            scanned = 0
            for line in handle:
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    warnings.add(path, "invalid_json_line")
                    continue
                if not isinstance(entry, dict):
                    warnings.add(path, "invalid_entry")
                    continue
                scanned += 1
                entries.append(entry)
    except (OSError, UnicodeError):
        if all_projects or scope_confirmed:
            warnings.add(path, "unreadable_file")
        return None

    active_ids = active_entry_ids(entries, version)
    if active_ids is None:
        warnings.add(path, "invalid_branch_structure")
        return None
    by_id = {
        entry["id"]: entry
        for entry in entries
        if isinstance(entry.get("id"), str)
    }
    active_entries = entries if version == 1 else [by_id[entry_id] for entry_id in active_ids]
    messages = [message for entry in active_entries if (message := recall_text(entry)) is not None]
    return messages, scanned


def permitted_files(
    roots: list[Path], warnings: session_search.WarningCollector
) -> list[Path]:
    discovered = session_search.discover_session_files(roots)
    allowed_roots = [Path(session_search.normalized_path(root)) for root in roots]
    result: list[Path] = []
    for path in discovered:
        resolved = Path(session_search.normalized_path(path))
        if not any(resolved == root or resolved.is_relative_to(root) for root in allowed_roots):
            warnings.add(path, "file_outside_session_root")
            continue
        result.append(resolved)
    return result


def candidate_sort_key(candidate: Candidate) -> tuple[int, int, datetime, str]:
    return (
        candidate.matched_terms,
        candidate.matching_messages,
        candidate.latest_match,
        str(candidate.path),
    )


def message_fingerprint(messages: Iterable[RecallMessage]) -> str:
    digest = hashlib.sha256()
    for message in messages:
        encoded = json.dumps(
            [message.entry_id, message.timestamp, message.role, message.text],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def cutoff_from_args(
    args: argparse.Namespace, now: datetime | None = None
) -> datetime | None:
    if args.days is None:
        return None
    if not math.isfinite(args.days) or args.days < 0:
        raise ValueError("--days must be a finite non-negative number")
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    try:
        return current_time.astimezone(timezone.utc) - timedelta(days=args.days)
    except OverflowError as error:
        raise ValueError("--days exceeds the supported date range") from error


def candidate_for_messages(
    path: Path,
    messages: list[RecallMessage],
    terms: tuple[str, ...],
    cutoff: datetime | None,
) -> tuple[Candidate | None, list[RecallMessage]]:
    eligible = [
        message for message in messages
        if cutoff is None
        or ((timestamp := session_search.parse_timestamp(message.timestamp)) is not None
            and timestamp >= cutoff)
    ]
    matched_terms: set[str] = set()
    matching_messages = 0
    latest_match = datetime.min.replace(tzinfo=timezone.utc)
    for message in eligible:
        timestamp = session_search.parse_timestamp(message.timestamp)
        searchable = message.text.casefold()
        present = {term for term in terms if term in searchable}
        if not present:
            continue
        matching_messages += 1
        matched_terms.update(present)
        if timestamp is not None and timestamp > latest_match:
            latest_match = timestamp
    if not matching_messages:
        return None, eligible
    return Candidate(
        path,
        matching_messages,
        len(matched_terms),
        latest_match,
        message_fingerprint(messages),
    ), eligible


def scan_candidates(
    args: argparse.Namespace,
    terms: tuple[str, ...],
    now: datetime | None = None,
) -> tuple[list[Candidate], dict[str, int], session_search.WarningCollector]:
    cutoff = cutoff_from_args(args, now)
    roots = [args.sessions_root, *args.additional_sessions_root]
    warnings = session_search.WarningCollector()
    paths = permitted_files(roots, warnings)
    target_cwd = session_search.normalized_path(args.cwd)
    current = (
        session_search.normalized_path(os.environ["PI_SESSION_FILE"])
        if os.environ.get("PI_SESSION_FILE")
        else None
    )
    candidates: list[Candidate] = []
    files_selected = 0
    scanned_entries = 0
    excluded_current = 0

    for path in paths:
        if not args.include_current and current and session_search.normalized_path(path) == current:
            excluded_current += 1
            continue
        loaded = read_active_messages(path, target_cwd, args.all_projects, warnings)
        if loaded is None:
            continue
        messages, scanned = loaded
        if scanned < 0:
            continue
        files_selected += 1
        scanned_entries += scanned
        candidate, _eligible = candidate_for_messages(path, messages, terms, cutoff)
        if candidate is not None:
            candidates.append(candidate)

    candidates.sort(key=candidate_sort_key, reverse=True)
    summary = {
        "files_selected": files_selected,
        "current_session_files_excluded": excluded_current,
        "entries_scanned": scanned_entries,
        "matched_sessions": len(candidates),
    }
    return candidates, summary, warnings


def matching_indices(messages: list[RecallMessage], terms: tuple[str, ...]) -> list[int]:
    return [
        index
        for index, message in enumerate(messages)
        if any(term in message.text.casefold() for term in terms)
    ]


def window_ranges(message_count: int, hits: list[int]) -> tuple[list[tuple[int, int]], bool]:
    ranges: list[tuple[int, int]] = []
    for hit in hits:
        start = max(0, hit - 1)
        end = min(message_count, hit + 2)
        if ranges:
            previous_start, previous_end = ranges[-1]
            if hit < previous_end:
                # The matching message is already represented; do not create
                # an overlapping window just to add another neighbor.
                continue
            if start <= previous_end:
                merged_end = max(previous_end, end)
                if merged_end - previous_start <= MAX_MESSAGES_PER_WINDOW:
                    ranges[-1] = (previous_start, merged_end)
                    continue
                start = previous_end
        ranges.append((start, end))
    truncated = len(ranges) > MAX_WINDOWS
    return ranges[:MAX_WINDOWS], truncated


def recall_windows(
    messages: list[RecallMessage], terms: tuple[str, ...]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    hits = matching_indices(messages, terms)
    ranges, windows_truncated = window_ranges(len(messages), hits)
    windows: list[dict[str, Any]] = []
    returned_bounds: list[tuple[int, int]] = []
    evidence_chars = 0
    represented_hits = 0
    previous_end = 0

    for start, end in ranges:
        items: list[dict[str, Any]] = []
        for index in range(start, end):
            message = messages[index]
            evidence = session_search.mask_and_shorten(
                message.text, limit=MAX_MESSAGE_CHARS, queries=terms
            )
            if evidence_chars + len(evidence) > MAX_TOTAL_EVIDENCE_CHARS:
                windows_truncated = True
                break
            evidence_chars += len(evidence)
            items.append({
                "role": message.role,
                "timestamp": message.timestamp,
                "evidence": evidence,
                "matches_term": index in hits,
            })
        if not items:
            break
        actual_end = start + len(items)
        represented_hits += sum(1 for hit in hits if start <= hit < actual_end)
        windows.append({
            "messages_omitted_before": start - previous_end,
            "messages": items,
            "messages_omitted_after": 0,
        })
        returned_bounds.append((start, actual_end))
        previous_end = actual_end
        if actual_end < end:
            break

    for index, window in enumerate(windows):
        _start, actual_end = returned_bounds[index]
        next_start = returned_bounds[index + 1][0] if index + 1 < len(returned_bounds) else len(messages)
        window["messages_omitted_after"] = max(0, next_start - actual_end)

    return windows, {
        "matching_messages": len(hits),
        "matching_messages_represented": represented_hits,
        "windows_returned": len(windows),
        "messages_returned": sum(len(window["messages"]) for window in windows),
        "evidence_chars": evidence_chars,
        "evidence_truncated": windows_truncated or represented_hits < len(hits),
    }


def add_scope_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--term", action="append", default=[], required=True,
                        help="case-insensitive literal recall term; repeat for alternatives (OR)")
    parser.add_argument("--days", type=float, help="include messages from the last N days")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--all-projects", action="store_true", help="search sessions from every project")
    scope.add_argument("--cwd", default=os.getcwd(), help="project cwd to match exactly (default: current cwd)")
    parser.add_argument("--include-current", action="store_true", help="include PI_SESSION_FILE (excluded by default)")
    parser.add_argument("--additional-sessions-root", type=Path, action="append", default=[], metavar="PATH",
                        help="also search this directory recursively; repeat for multiple directories")
    parser.add_argument("--sessions-root", type=Path, default=session_search.DEFAULT_SESSIONS_ROOT,
                        help=argparse.SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    parser = session_search.SessionArgumentParser(
        description="Find or recall bounded evidence from active branches of local Pi sessions."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)
    find = subparsers.add_parser("find", help="rank matching sessions without returning conversation evidence")
    add_scope_arguments(find)
    find.add_argument("--limit", type=int, default=DEFAULT_CANDIDATE_LIMIT,
                      help=f"maximum candidates to return (default: {DEFAULT_CANDIDATE_LIMIT})")

    recall = subparsers.add_parser("recall", help="return bounded windows from one ranked candidate")
    add_scope_arguments(recall)
    recall.add_argument("--candidate-rank", type=int, default=1,
                        help="ranked candidate to recall (default: 1)")
    recall.add_argument("--include-evidence", action="store_true", required=True,
                        help="include masked conversation snippets; requires explicit user consent in agent workflows")
    return parser


def scope_view(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "all_projects": args.all_projects,
        "days": args.days,
        "include_current": args.include_current,
        "branch_scope": "active",
    }


def find_output(args: argparse.Namespace, now: datetime | None = None) -> dict[str, Any]:
    terms = normalize_terms(args.term)
    if args.limit < 1 or args.limit > MAX_CANDIDATE_LIMIT:
        raise ValueError("candidate limit is invalid")
    candidates, summary, warnings = scan_candidates(args, terms, now)
    returned = candidates[:args.limit]
    summary.update({
        "candidates_returned": len(returned),
        "candidate_limit": args.limit,
        "candidates_truncated": len(candidates) > len(returned),
    })
    return {
        "status": "ok",
        "mode": "find",
        "evidence_included": False,
        "scope": scope_view(args),
        "summary": summary,
        "candidates": [
            {
                "rank": rank,
                "matched_terms": candidate.matched_terms,
                "matching_messages": candidate.matching_messages,
            }
            for rank, candidate in enumerate(returned, 1)
        ],
        "results": [],
        "warnings": warnings.output(False),
    }


def recall_output(args: argparse.Namespace, now: datetime | None = None) -> dict[str, Any]:
    terms = normalize_terms(args.term)
    if args.candidate_rank < 1 or args.candidate_rank > MAX_CANDIDATE_LIMIT:
        raise ValueError("candidate rank is invalid")
    reference_time = now or datetime.now(timezone.utc)
    candidates, scan_summary, warnings = scan_candidates(args, terms, reference_time)
    if args.candidate_rank > len(candidates):
        raise CandidateNotFoundError
    candidate = candidates[args.candidate_rank - 1]
    loaded = read_active_messages(
        candidate.path,
        session_search.normalized_path(args.cwd),
        args.all_projects,
        warnings,
    )
    if loaded is None or loaded[1] < 0:
        raise CandidateNotFoundError
    messages, _scanned = loaded
    refreshed, eligible = candidate_for_messages(
        candidate.path, messages, terms, cutoff_from_args(args, reference_time)
    )
    if refreshed != candidate:
        raise CandidateNotFoundError

    windows, evidence_summary = recall_windows(eligible, terms)
    summary = {
        **scan_summary,
        "selected_candidate_rank": args.candidate_rank,
        **evidence_summary,
    }
    return {
        "status": "ok",
        "mode": "recall",
        "evidence_included": True,
        "scope": scope_view(args),
        "summary": summary,
        "results": windows,
        "warnings": warnings.output(False),
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        output = find_output(args) if args.mode == "find" else recall_output(args)
    except (session_search.InvalidArgumentError, ValueError):
        return session_search.emit_error("INVALID_ARGUMENT", "Arguments are invalid.")
    except CandidateNotFoundError:
        return session_search.emit_error("CANDIDATE_NOT_FOUND", "The selected candidate is unavailable.")
    except (OSError, RuntimeError):
        return session_search.emit_error("SESSION_STORAGE_UNAVAILABLE", "Session storage could not be read.")
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
