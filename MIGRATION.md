# Pi Agent Kit migration

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

## v0.4.0

Pi Agent Kit remains a source-first collection, not an install-everything package. This release moves Pi Subagent and Pi Jev maintenance to their independent repositories and moves SimplyKST to `retired/`.

The kit's `v0.4.0` tag and GitHub Release are independent of the Pi Subagent npm package version. This kit release does not publish an npm package or change an installed Pi environment.

### Independent sources

| Former kit path | New maintained source |
| --- | --- |
| `live/extensions/pi-subagent/` | [pi-subagent/extensions/pi-subagent](https://github.com/MDGChamomile/pi-subagent/tree/main/extensions/pi-subagent) |
| `live/skills/pi-subagent/` | [pi-subagent/skills/pi-subagent](https://github.com/MDGChamomile/pi-subagent/tree/main/skills/pi-subagent) |
| `packaging/pi-subagent/` | [pi-subagent/packaging/pi-subagent](https://github.com/MDGChamomile/pi-subagent/tree/main/packaging/pi-subagent) |
| `live/extensions/pi-jev-router/` | [pi-jev/extensions/pi-jev-router](https://github.com/MDGChamomile/pi-jev/tree/main/extensions/pi-jev-router) |
| `live/extensions/pi-jev-tools/` | [pi-jev/extensions/pi-jev-tools](https://github.com/MDGChamomile/pi-jev/tree/main/extensions/pi-jev-tools) |
| `live/skills/pi-jev/` | [pi-jev/skills/pi-jev](https://github.com/MDGChamomile/pi-jev/tree/main/skills/pi-jev) |

The new repositories retain the relevant source history. These paths, the kit's npm publishing workflow, and its subagent canary and Jev/subagent validation jobs are removed from the current kit tree. Earlier kit commits, tags, and releases remain available; they are historical snapshots, not the maintained source.

### Existing installations

#### Pi Subagent from npm

The package name remains `@mdgchamomile/pi-subagent`. Its independent `0.4.0` release is already available; no new package name is required. Use the [new project guide](https://github.com/MDGChamomile/pi-subagent) for requirements and installation. Updating this kit checkout does not upgrade an npm installation.

#### Source copies and symlinks

Before updating a kit checkout used by an active installation:

1. Check whether copied files, symlinks, Pi settings, or launchers refer to one of the former paths above.
2. Review the new project's migration guide: [Pi Subagent](https://github.com/MDGChamomile/pi-subagent/blob/main/MIGRATION.md) or [Pi Jev](https://github.com/MDGChamomile/pi-jev/blob/main/MIGRATION.md).
3. Migrate local customizations deliberately. Replace the Subagent extension and companion skill together; for Jev, keep the shared skill and whichever extensions you use. Do not overlay old and new source trees or load duplicate copies.
4. Update source-path references explicitly and reload or restart Pi after the installation is ready.

A copied installation remains where it was copied, but it will not receive future updates from the kit. A symlink or launcher targeting a removed kit path can break when this checkout is updated. Git does not repair those references or move installed resources. This release does not perform that migration for you.

Pi Jev remains source-distributed, with either or both consent-gated extensions independently loadable. It is not an npm package and does not require Pi Subagent as a runtime or development dependency.

### SimplyKST

SimplyKST is retained as reference material at [`retired/skills/simplykst/`](retired/skills/simplykst/README.md), no longer actively maintained or included in live validation. An existing copy is not uninstalled. Update or retire any local installation deliberately rather than assuming the directory move changes it.

### What stays in the kit

The maintained resources remain:

- [`pi-compaction-model`](live/extensions/pi-compaction-model/README.md)
- [`deep-plan`](live/skills/deep-plan/README.md)
- [`session-search`](live/skills/session-search/README.md)

The `live-validation` workflow continues to check these resources using the [documented offline checks](CONTRIBUTING.md#verification-entry-points). `security-audit` has since moved to [`retired/skills/security-audit/`](retired/skills/security-audit/README.md); moving the source does not uninstall existing copies. Existing retired resources, their licenses, and the repository's historical releases remain intact.
