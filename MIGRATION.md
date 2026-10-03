# Pi Agent Kit migration

## Unreleased

### Compaction extension minimum Pi version

`pi-compaction-model` now requires Pi 1.0.0 or later (`peerDependencies: >=1.0.0`), raised from `>=0.80.7`. Its offline checks now pin Pi 1.0.0. Update Pi before adopting this version of the extension; keep an earlier copy if you must stay on an older Pi. Runtime behavior, including the single-retry policy, is unchanged.

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
