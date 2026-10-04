# Pi Agent Kit migration

## v0.7.1

This remains a source-only GitHub release, not an npm package or an automatic update of installed Pi resources. Review the changes and update only the resources you adopt; preserve local customizations.

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
