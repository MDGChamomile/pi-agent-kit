#!/usr/bin/env python3
"""Find and recall bounded evidence from active branches of local Pi sessions."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
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


class RecallReadError(RuntimeError):
    """Disclosed read failures prevent verifying an empty recall."""


def normalize_terms(values: Iterable[str]) -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip().casefold()
        if len(normalized) < MIN_TERM_CHARS or len(normalized) > MAX_TERM_CHARS:
            raise ValueError("recall terms have invalid lengths")
        if normalized not in seen:
            seen.add(normalized)
            terms.append(normalized)
    if not terms or len(terms) > MAX_TERMS:
        raise ValueError("recall requires a bounded number of terms")
    return tuple(terms)


def matching_terms(text: str, terms: tuple[str, ...]) -> set[str]:
    searchable = text.casefold()
    return {term for term in terms if term in searchable}


def active_entries(entries: list[dict[str, Any]], version: int) -> list[dict[str, Any]] | None:
    if version == 1:
        return entries

    by_id: dict[str, dict[str, Any]] = {}
    leaf_id: str | None = None
    for entry in entries:
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or entry_id in by_id:
            return None
        parent_id = entry.get("parentId")
        if parent_id is not None and not isinstance(parent_id, str):
            return None
        by_id[entry_id] = entry
        leaf_id = entry_id

    if leaf_id is None:
        return []
    path: list[dict[str, Any]] = []
    seen: set[str] = set()
    current: str | None = leaf_id
    while current is not None:
        if current in seen or current not in by_id:
            return None
        seen.add(current)
        path.append(by_id[current])
        current = by_id[current].get("parentId")
    path.reverse()
    return path


def recall_text(entry: dict[str, Any]) -> RecallMessage | None:
    if entry.get("type") != "message" or not isinstance(entry.get("message"), dict):
        return None
    message = entry["message"]
    role = message.get("role")
    if not isinstance(role, str) or role not in {"user", "assistant"}:
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


def retain_recall_entry(entry: dict[str, Any]) -> dict[str, Any]:
    # Keep every node for branch validation, but not its unused payloads.
    retained = {
        key: entry[key]
        for key in ("type", "id", "parentId", "timestamp")
        if key in entry
    }
    message = entry.get("message")
    if entry.get("type") == "message" and isinstance(message, dict):
        role = message.get("role")
        retained["message"] = {"role": role}
        if role in ("user", "assistant"):
            # Preserve the full searchable text; output limits apply later.
            retained["message"]["content"] = session_search.text_content(message.get("content"))
    return retained


def read_active_messages(
    path: Path,
    target_cwd: str,
    all_projects: bool,
    warnings: session_search.WarningCollector,
) -> tuple[list[RecallMessage], int] | None:
    scope_confirmed = False
    try:
        # Decode only the header line before deciding scope. TextIOWrapper can
        # decode body bytes ahead of readline() and hide an in-scope failure.
        with path.open("rb") as handle:
            header = session_search.read_session_header(handle)
            if header is None:
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
                    entry = json.loads(line.decode("utf-8"))
                except (json.JSONDecodeError, TypeError):
                    warnings.add(path, "invalid_json_line")
                    continue
                if not isinstance(entry, dict):
                    warnings.add(path, "invalid_entry")
                    continue
                scanned += 1
                entries.append(retain_recall_entry(entry))
    except (OSError, UnicodeError):
        if all_projects or scope_confirmed:
            warnings.add(path, "unreadable_file")
        return None

    branch = active_entries(entries, version)
    if branch is None:
        warnings.add(path, "invalid_branch_structure")
        return None
    messages = [message for entry in branch if (message := recall_text(entry)) is not None]
    return messages, scanned


def permitted_files(
    roots: list[Path], warnings: session_search.WarningCollector
) -> list[Path]:
    discovered = session_search.discover_session_files(
        roots, on_outside=lambda path: warnings.add(path, "file_outside_session_root"),
    )
    return [Path(session_search.normalized_path(path)) for path in discovered]


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


def candidate_for_messages(
    path: Path,
    messages: list[RecallMessage],
    terms: tuple[str, ...],
    cutoff: datetime | None,
    until: datetime | None = None,
    *,
    fingerprint: bool = True,
) -> tuple[Candidate | None, list[RecallMessage]]:
    """Find omits the fingerprint; recall needs it to detect a changed candidate."""
    time_range = session_search.TimeRange(cutoff, until)
    eligible: list[RecallMessage] = []
    matched_terms: set[str] = set()
    matching_messages = 0
    latest_match = datetime.min.replace(tzinfo=timezone.utc)
    for message in messages:
        timestamp = session_search.parse_timestamp(message.timestamp)
        if not time_range.contains(timestamp):
            continue
        eligible.append(message)
        present = matching_terms(message.text, terms)
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
        message_fingerprint(messages) if fingerprint else "",
    ), eligible


def scan_candidates(
    args: argparse.Namespace,
    terms: tuple[str, ...],
    now: datetime | None = None,
    *, time_range: session_search.TimeRange | None = None,
    exclusions: frozenset[str] | None = None,
    fingerprints: bool = True,
) -> tuple[list[Candidate], dict[str, int], session_search.WarningCollector]:
    if time_range is None:
        time_range = session_search.time_range_for_args(args, now)
    if exclusions is None:
        exclusions = session_search.normalized_exclusions(args.exclude_session_file)
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
    excluded_explicit = 0
    matched_exclusions: set[str] = set()

    for path in paths:
        path_key = str(path)  # permitted_files already normalizes discovered paths.
        if path_key in exclusions:
            matched_exclusions.add(path_key)
        if not args.include_current and current and path_key == current:
            excluded_current += 1
            continue
        if path_key in exclusions:
            excluded_explicit += 1
            continue
        loaded = read_active_messages(path, target_cwd, args.all_projects, warnings)
        if loaded is None:
            continue
        messages, scanned = loaded
        if scanned < 0:
            continue
        files_selected += 1
        scanned_entries += scanned
        candidate, _eligible = candidate_for_messages(
            path, messages, terms, time_range.since, time_range.until, fingerprint=fingerprints,
        )
        if candidate is not None:
            candidates.append(candidate)

    # Only disclosed, in-scope failures can invalidate an empty result. Unknown
    # or foreign-project files retain their existing private warning policy.
    if not candidates and warnings.output(False)["by_kind"].get("unreadable_file", 0):
        raise RecallReadError("read failures prevent verifying an empty recall")

    candidates.sort(key=candidate_sort_key, reverse=True)
    summary = {
        "files_selected": files_selected,
        "current_session_files_excluded": excluded_current,
        **session_search.exclusion_summary(exclusions, matched_exclusions, excluded_explicit),
        "entries_scanned": scanned_entries,
        "matched_sessions": len(candidates),
    }
    return candidates, summary, warnings


def matching_indices(messages: list[RecallMessage], terms: tuple[str, ...]) -> list[int]:
    return [
        index
        for index, message in enumerate(messages)
        if matching_terms(message.text, terms)
    ]


def window_ranges(
    message_count: int, hits: list[int], window_start: int = 0,
) -> tuple[list[tuple[int, int]], bool]:
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
    next_start = window_start + MAX_WINDOWS
    return ranges[window_start:next_start], len(ranges) > next_start


def recall_windows(
    messages: list[RecallMessage], terms: tuple[str, ...], window_start: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, Any], bool]:
    hits = matching_indices(messages, terms)
    ranges, has_more_windows = window_ranges(len(messages), hits, window_start)
    windows_truncated = has_more_windows
    windows: list[dict[str, Any]] = []
    returned_bounds: list[tuple[int, int]] = []
    evidence_chars = 0
    represented_hits = 0
    previous_end = 0

    for start, end in ranges:
        items: list[dict[str, Any]] = []
        for index in range(start, end):
            message = messages[index]
            evidence, text_truncated = session_search.mask_and_shorten_with_metadata(
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
                "text_truncated": text_truncated,
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
    }, has_more_windows


def add_scope_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--term", action="append", default=[], required=True,
                        help="case-insensitive literal recall term; repeat for alternatives (OR)")
    session_search.add_time_arguments(parser)
    session_search.add_storage_scope_arguments(parser)
    session_search.add_exclusion_argument(parser)


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
    selection = recall.add_mutually_exclusive_group()
    selection.add_argument("--candidate-rank", type=int, default=1,
                           help="ranked candidate to recall (default: 1)")
    selection.add_argument("--continuation", metavar="TOKEN",
                           help="read the next matching windows from a previous recall; reuse its terms and scope")
    recall.add_argument("--include-evidence", action="store_true", required=True,
                        help="include masked conversation snippets; requires explicit user consent in agent workflows")
    return parser


def scope_view(args: argparse.Namespace, time_range: session_search.TimeRange) -> dict[str, Any]:
    return {
        "all_projects": args.all_projects,
        "days": args.days,
        **time_range.view(),
        "include_current": args.include_current,
        "branch_scope": "active",
    }


def find_output(args: argparse.Namespace, now: datetime | None = None) -> dict[str, Any]:
    terms = normalize_terms(args.term)
    if args.limit < 1 or args.limit > MAX_CANDIDATE_LIMIT:
        raise ValueError("candidate limit is invalid")
    time_range = session_search.time_range_for_args(args, now)
    candidates, summary, warnings = scan_candidates(args, terms, time_range=time_range, fingerprints=False)
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
        "scope": scope_view(args, time_range),
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


def continuation_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def continuation_scope(
    args: argparse.Namespace, terms: tuple[str, ...], reference_time: datetime,
    time_range: session_search.TimeRange, exclusions: frozenset[str],
) -> str:
    current = os.environ.get("PI_SESSION_FILE")
    # Preserve legacy digests when neither new option is used.
    absolute_bounds = time_range.view() if args.since is not None or args.until is not None else {}
    return continuation_digest({
        **absolute_bounds,
        **({"excluded_session_files": sorted(exclusions)} if exclusions else {}),
        "roots": sorted({session_search.normalized_path(root) for root in
                         [args.sessions_root, *args.additional_sessions_root]}),
        "cwd": None if args.all_projects else session_search.normalized_path(args.cwd),
        "all_projects": args.all_projects,
        "include_current": args.include_current,
        "excluded_current": session_search.normalized_path(current)
                            if current and not args.include_current else None,
        "days": args.days,
        "terms": sorted(terms),
        "reference_time": reference_time.isoformat(),
    })


def continuation_candidate(candidate: Candidate, scope: str) -> str:
    # A one-way digest, not an encoded path or a globally reusable message hash.
    return continuation_digest([scope, str(candidate.path), candidate.message_fingerprint])


def decode_continuation(token: str) -> tuple[datetime, str, str, int]:
    try:
        if len(token) > 512:
            raise ValueError
        raw = base64.b64decode(token.encode("ascii"), altchars=b"-_", validate=True)
        value = json.loads(raw)
        if not isinstance(value, list) or len(value) != 5 or type(value[0]) is not int or value[0] != 1:
            raise ValueError
        _, timestamp, scope, candidate, offset = value
        reference_time = session_search.parse_timestamp(timestamp)
        if reference_time is None or timestamp != reference_time.isoformat():
            raise ValueError
        if any(not isinstance(digest, str) or len(digest) != 64
               or any(char not in "0123456789abcdef" for char in digest)
               for digest in (scope, candidate)):
            raise ValueError
        if type(offset) is not int or offset <= 0 or offset > 2**31 or offset % MAX_WINDOWS:
            raise ValueError
        return reference_time, scope, candidate, offset
    except (ValueError, TypeError, UnicodeError, binascii.Error, RecursionError) as error:
        raise ValueError("continuation is invalid") from error


def recall_output(args: argparse.Namespace, now: datetime | None = None) -> dict[str, Any]:
    terms = normalize_terms(args.term)
    if args.candidate_rank < 1 or args.candidate_rank > MAX_CANDIDATE_LIMIT:
        raise ValueError("candidate rank is invalid")
    reference_time = now or datetime.now(timezone.utc)
    reference_time = (reference_time.replace(tzinfo=timezone.utc) if reference_time.tzinfo is None
                      else reference_time.astimezone(timezone.utc))
    window_start = 0
    expected_candidate = None
    expected_scope = None
    if args.continuation is not None:
        reference_time, expected_scope, expected_candidate, window_start = decode_continuation(args.continuation)
    time_range = session_search.time_range_for_args(args, reference_time)
    exclusions = session_search.normalized_exclusions(args.exclude_session_file)
    scope = continuation_scope(args, terms, reference_time, time_range, exclusions)
    if expected_scope is not None and scope != expected_scope:
        raise ValueError("continuation scope changed")
    candidates, scan_summary, warnings = scan_candidates(args, terms, time_range=time_range, exclusions=exclusions)
    if expected_candidate is not None:
        selected = [
            (rank, candidate) for rank, candidate in enumerate(candidates, 1)
            if continuation_candidate(candidate, scope) == expected_candidate
        ]
        if len(selected) != 1:
            raise CandidateNotFoundError
        selected_rank, candidate = selected[0]
    else:
        if args.candidate_rank > len(candidates):
            raise CandidateNotFoundError
        selected_rank = args.candidate_rank
        candidate = candidates[selected_rank - 1]
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
        candidate.path, messages, terms, time_range.since, time_range.until
    )
    if refreshed != candidate:
        raise CandidateNotFoundError

    windows, evidence_summary, has_more = recall_windows(eligible, terms, window_start)
    if not windows:
        raise CandidateNotFoundError
    next_continuation = None
    if has_more:
        cursor = [1, reference_time.isoformat(), scope,
                  continuation_candidate(candidate, scope), window_start + MAX_WINDOWS]
        next_continuation = base64.urlsafe_b64encode(
            json.dumps(cursor, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
    summary = {
        **scan_summary,
        "selected_candidate_rank": selected_rank,
        **evidence_summary,
    }
    return {
        "status": "ok",
        "mode": "recall",
        "evidence_included": True,
        "next_continuation": next_continuation,
        "scope": scope_view(args, time_range),
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
    except RecallReadError:
        return session_search.emit_error(
            "SESSION_STORAGE_UNAVAILABLE",
            "One or more in-scope session files could not be read, so the requested history could not be verified.",
        )
    except (OSError, RuntimeError):
        return session_search.emit_error("SESSION_STORAGE_UNAVAILABLE", "Session storage could not be read.")
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
