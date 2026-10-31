# Pi Agent Kit migration

## v0.8.0

This remains a source-only GitHub release, not an npm package or an automatic update of installed Pi resources. Review the changes, preserve local customizations, and update only the resources you adopt. Restart Pi or use `/reload` after updating auto-discovered resources. No stored-session or execution-record migration is required.

### Compaction retry policy and provider routing

The compaction extension now follows Pi's `retry` settings instead of retrying the entire compaction once after one second. Review `retry.enabled`, `retry.maxRetries`, `retry.baseDelayMs`, and `retry.maxAgentDelayMs` before updating: request counts, waiting time, and provider usage can change. Setting `retry.enabled: false` now disables these retries. Split-turn compaction retries only the failed summarization request, rather than repeating a completed part. Exhausted retries still return control to Pi's native handling path.

Summarization now uses Pi's model-registry stream path, including extension-registered providers and provider-specific authentication. The `compactionModel` configuration format and minimum Pi version (`>=1.0.0`) are unchanged. See the [compaction guide](live/extensions/pi-compaction-model/README.md).

### Session search

Update the whole skill directory, including the new shared `scripts/session_common.py` module, rather than copying only a CLI script. Tool results are correlated with ancestral calls, decoded tool-argument evidence is masked, and malformed JSON, decoder depth failures, and Unicode edge cases are isolated. Time boundaries consistently reject hour 24, including on Python 3.14.

Continuation scope digests now always include time boundaries and file exclusions. Tokens from older helper versions may fail with `INVALID_ARGUMENT`; rerun `find` and start a new recall instead of reusing an old token. Recalled conclusions remain historical claims, not current project facts or authorization. See the [session-search guide](live/skills/session-search/README.md).

### Deep-plan and maintenance

Deep-plan shares CLI entrypoint detection through `scripts/entrypoint.mjs`; copy the complete skill directory when updating. Record locations and publication behavior are unchanged. Tests, maintained-link validation, and contributor/review documentation have also been consolidated.

## v0.7.2

This remains a source-only GitHub release, not an npm package or an automatic update of installed Pi resources. Review the changes, preserve local customizations, and update only the resources you adopt. Restart Pi or use `/reload` after updating auto-discovered resources. No data migration is required.

### Session search

Aggregate warnings now respect the selected project: files with an unreadable header or a different cwd no longer contribute warning counts or paths in the default scope. Use `--all-projects` when checking for damaged files across projects. Search and recall also skip unnecessary argument serialization and candidate fingerprinting without changing the intended result semantics.

Argument parsing now follows standard argparse behavior. Pass dash-prefixed strings with `=`, for example `--query=-inf`, `--term=-nan`, or `--cwd=-infinity`; quoting a separate value does not change parsing. `--days` still accepts only finite, non-negative numbers. See the [session-search guide](live/skills/session-search/README.md).

### Compaction extension and contributor workflow

The compaction extension's runtime behavior and minimum Pi version are unchanged. Its model-reference tests now exercise the real lookup path; the unused build script and a test-only re-export were removed.

Validation now checks maintained relative Markdown links and limits push-triggered runs to `main` and `updates`; every PR still receives validation. Contributor documentation clarifies task branches, review completion, and release-history handling.

## v0.7.1

This remains a source-only GitHub release, not an npm package or an automatic update of installed Pi resources. Review the changes and update only the resources you adopt; preserve local customizations. Restart Pi or use `/reload` after updating auto-discovered resources.

### Session search

Aggregate, batch, `find`, and `recall` now accept fixed `--since` (inclusive) and `--until` (exclusive) timestamp boundaries with an explicit timezone. They cannot be combined with `--days`; invalid boundaries fail before session discovery. Fractional timestamps are normalized consistently on Python 3.10 and later.

Use repeatable `--exclude-session-file PATH` to skip explicitly selected session files before their headers or bodies are opened. This is exact normalized path matching, not a glob, directory prefix, or session ID filter. Automatic current-session exclusion is unchanged. See the [session-search guide](live/skills/session-search/README.md#time-ranges) for time ranges and [file exclusions](live/skills/session-search/README.md#exclude-specific-session-files) for matching and count semantics.

### Contributor workflow

PRs gain a Summary / Verification / Risk template and clearer review-completion guidance. Pullfrog remains review-only, including owner-authorized external-contributor PR reviews. PR validation no longer uses workflow-level path filtering, so required checks can be reported for every PR.

## v0.7.0

This remains a source-only GitHub release, not an npm package or an automatic update of installed Pi resources. Review the changed resources, preserve local customizations, and update only the copies you adopt. Restart Pi or use `/reload` after updating auto-discovered resources.

### Compaction extension minimum Pi version

`pi-compaction-model` now requires Pi 1.0.0 or later (`peerDependencies: >=1.0.0`), raised from `>=0.80.7`. Its offline checks now pin Pi 1.0.0. Update Pi before adopting this version of the extension; keep an earlier copy if you must stay on an older Pi. Runtime behavior, including the single-retry policy, is unchanged.

### Retired resources

The `retired/` directory is no longer in the current tree; the [README](README.md#retired) links each resource's last version in the repository history. Existing copies are not removed, but a symlink or launcher that targets a `retired/` path in this checkout breaks when the checkout is updated. Copy the resource from history first if you still use it.

## v0.6.0

This remains a source-only GitHub release, not an npm package or an automatic update of installed Pi resources. Review the changed resources, preserve local customizations and existing records, and update only the copies you adopt. Restart Pi or use `/reload` after updating auto-discovered resources.

### Deep-plan records

New execution records default to external user state rather than the installed skill directory. Destination precedence is:

1. An explicit destination in the request, used directly for that run.
2. `PI_DEEP_PLAN_RECORDS_DIR`, partitioned by project.
3. An absolute `XDG_STATE_HOME`, with `pi/deep-plan/records/<project-key>/` appended.
4. `~/.local/state/pi/deep-plan/records/<project-key>/`.

The skill does not edit settings or move existing records. Keep historical skill-local, external, and flat-format records where they are; updating the skill does not migrate them. The selected destination must be writable and support hard links, while the installation itself can be read-only. See the [record contract](live/skills/deep-plan/references/execution-record.md) for collision and publication behavior.

### Session search

The helpers now honor Pi's session storage environment overrides and explicit additional roots. If Pi uses a CLI `--session-dir` or a `sessionDir` setting, pass that location as `--sessions-root`; the helpers do not read Pi settings. See the [storage guide](live/skills/session-search/README.md#additional-session-directories).

Recorded `SKILL.md` reads are recognized outside standard skill directories, with branch-local recorded identities. Aggregate search also counts Pi 0.99+ `nestedCalls`; missing arguments cannot identify skill reads, and incomplete or omitted calls cannot be reconstructed. Updating the helper does not backfill metadata absent from older sessions. Default summaries remain path-free, and evidence still requires explicit disclosure consent.

### Compaction extension

OpenRouter attribution now matches parsed hostnames, including subdomains and a single terminal DNS root dot, rather than URL substrings. Named-provider detection, telemetry gating, and configured-header precedence are unchanged. Runtime dependencies are still supplied by Pi; no dependency installation is required to adopt the source copy. The declared minimum remains `>=0.80.7`, not a tested compatibility matrix. See the [extension guide](live/extensions/pi-compaction-model/README.md).
