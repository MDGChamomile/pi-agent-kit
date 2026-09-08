# Session Search

`session-search` is an [Agent Skill](https://agentskills.io/) for factual analysis across multiple local [Pi](https://github.com/earendil-works/pi) session files. Its helper script can count matching entries, identify repeated tool errors, and distinguish direct skill invocations from reads of a skill's `SKILL.md`.

Read [`SKILL.md`](SKILL.md) for the executable agent workflow. Use Pi's built-in `/resume` command instead when you only need to find, open, or continue one session.

## Safety model

- Reads session JSONL files without changing them or building an index.
- Searches only sessions whose recorded working directory exactly matches the current directory by default.
- Excludes the active session by default when `PI_SESSION_FILE` is set.
- Returns a path-free aggregate summary by default.
- Returns bounded, best-effort-masked evidence only with `--include-evidence`.
- Uses only the Python standard library and makes no network requests.

Session data is inherently sensitive. In an agent workflow, local tool output becomes context for the active model and may therefore reach a remote model provider. A cross-session request authorizes the default aggregate only. Use `--include-evidence` only after the user explicitly approves sending masked snippets, local paths, session identifiers, and warning paths to that provider. Masking cannot recognize every credential or personal detail.

## Requirements

- Pi session files under `~/.pi/agent/sessions`
- Python 3.10 or later

The parser supports Pi session versions 1 through 3. It treats a missing version as legacy v1 with a warning and skips newer, unsupported versions visibly instead of guessing at their structure.

## Installation

From the repository root, copy this directory into one of Pi's skill locations, for example:

```bash
mkdir -p ~/.pi/agent/skills
cp -R live/skills/session-search ~/.pi/agent/skills/
```

Restart Pi after installing it. Pi will expose the skill as `/skill:session-search` when skill commands are enabled.

## Script usage

The agent normally runs the helper script for you. You can also invoke it directly:

```bash
python3 ~/.pi/agent/skills/session-search/scripts/session_search.py --help
```

Run these examples from the project directory whose sessions you want to search, using the installed script's absolute path. Do not change into the skill directory to run it: the default project filter uses your current working directory, not the script's location. Use `--cwd /path/to/project` to select another project explicitly.

```bash
# Count matching events in sessions for the current project (safe default)
python3 ~/.pi/agent/skills/session-search/scripts/session_search.py --query timeout

# Explicitly request the same path-free summary mode
python3 ~/.pi/agent/skills/session-search/scripts/session_search.py --query timeout --summary-only

# Include representative evidence after explicit disclosure approval
python3 ~/.pi/agent/skills/session-search/scripts/session_search.py --days 7 --error --tool bash --include-evidence

# Compare direct invocations with SKILL.md reads across all projects
python3 ~/.pi/agent/skills/session-search/scripts/session_search.py --all-projects --skill deep-plan
```

### Additional session directories

By default, only `~/.pi/agent/sessions` is searched. Add other directories explicitly; no archive location is assumed:

```bash
python3 ~/.pi/agent/skills/session-search/scripts/session_search.py \
  --additional-sessions-root /path/to/session-backup \
  --additional-sessions-root /path/to/another-store
```

`--additional-sessions-root PATH` is repeatable and additive, not a replacement for the default directory. `~` is expanded; relative paths are resolved from the invocation's working directory. The same cwd, time, event, current-session exclusion, and evidence-consent rules apply across all directories. `--all-projects` selects all projects within those directories, not other storage locations.

Repeated or overlapping directories and file symlink aliases are deduplicated by resolved file path before counting. Separate copies (including files with the same session ID) and hard links remain separate files. Nested directory symlinks are not followed; a directory symlink explicitly supplied as a root is supported. Missing or non-directory roots and directory traversal failures return a path-free `SESSION_STORAGE_UNAVAILABLE` error (exit code 2), rather than a partial summary. Empty directories are valid. Individual unreadable session files retain the existing warning behavior.

For recurring agent use, specify your additional directories in your own local instructions. Keep personal paths out of the shared skill; this feature neither moves sessions nor changes Pi's `/resume` storage.

Repeated `--query` values use AND logic. Repeated `--role`, `--tool`, and `--skill` values are alternatives within each filter.

With `--include-evidence`, each snippet stays within 300 characters, including omission markers. The full evidence text is masked before whitespace is collapsed and a window is selected. For long text, the window centers on the earliest remaining query occurrence (case-insensitive, with query whitespace collapsed too), regardless of query order. Distant AND terms need not all appear in that single window; matching still uses the full original searchable event. If no query remains visible—for example, it was masked or matched only tool metadata—or no query was supplied, the snippet uses the masked text's beginning. Hidden values are never restored. Results remain newest first.

Assistant failures are counted by `--error` even when their content is empty. Their `errorMessage` text is searchable alongside any partial response and is subject to the same opt-in evidence and masking rules.

The command emits one JSON object:

| Field | Safe default | With `--include-evidence` |
| --- | --- | --- |
| `scope` | Path-free project selection and time range | Also includes the exact cwd |
| `summary` | Scan and match counts grouped by role, tool, and skill | Also reports evidence truncation |
| `results` | Empty | Bounded representative evidence, newest first |
| `warnings` | Deduplicated counts by kind | Up to 100 file-path details |

In `summary`, `tool_errors` counts matching error events per tool; `tool_error_sessions` counts session files with at least one such event per tool, using the same filters and case-insensitive tool names. Repeated failures of one tool in one file count once in `tool_error_sessions`. Files with identical session IDs still count separately; branches, copies, and retries are not deduplicated into inferred bugs or tasks. `matched_sessions` remains the overall matching-file count, not a per-tool distribution.

In `summary`, `evidence_omitted` distinguishes the safe default from `evidence_truncated`; `truncated` remains a compatibility alias for evidence truncation.

`--summary-only` remains as an explicit alias for the safe default. `--include-evidence` is mutually exclusive with it. A direct skill invocation is counted only for a user message matching Pi's complete skill envelope; this means the recorded message matches Pi's invocation envelope, not that provenance can be distinguished from identical XML pasted manually. Direct calls are reported separately from `SKILL.md` read attempts, successes, and errors. The legacy `skill_file_reads` counter remains an alias for attempts. Reading instructions, quoting partial XML, or mentioning a skill is not evidence that the skill was invoked.

## Known limitations

- Searches are case-insensitive literal matches, not regular expressions or semantic search.
- Counts describe recorded events and entries, not inferred tasks or outcomes.
- For v2 and v3, the latest branch marker is inferred from the parent chain of the last recorded entry; v1 is treated as a linear sequence.
- Every candidate file is opened once. Only its header is read until cwd and version selection succeeds; each selected body is then scanned once. There is no persistent index. Memory includes the discovered file paths used for deduplication, compact per-session branch metadata, aggregate counters, warning caps, call-correlation metadata, and the requested result limit.
- Secret masking is deliberately best-effort and is not a data-loss-prevention guarantee.

## Tests

From this directory:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

## License

MIT, as provided by the repository-level `LICENSE` file.
