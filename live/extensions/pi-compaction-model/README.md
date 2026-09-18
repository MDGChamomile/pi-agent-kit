# pi-compaction-model

A minimal extension for [Pi Coding Agent](https://github.com/earendil-works/pi) that lets native compaction use a dedicated model and thinking level.

It does not introduce a new summarization pipeline. It calls Pi's exported `compact()` implementation with the configured model, preserving Pi's native:

- prompts and structured summary format
- cut-point and recent-message retention behavior
- iterative previous-summary updates
- split-turn summaries
- file-operation tracking
- output-token budgeting
- `/compact` focus instructions

If the extension cannot produce a dedicated-model result, it returns control to Pi's native handling path. It does not start or guarantee a second compaction request itself.

## Origin and maintenance

This is an independently maintained derivative of [JMHSV/pi-compaction-model](https://github.com/JMHSV/pi-compaction-model), not an official upstream successor. Original copyright and MIT terms are preserved in [LICENSE](LICENSE).

Imported from revision `283f0de4fe56d4cc35931e1255e0d3888761426b`, including [upstream PR #1](https://github.com/JMHSV/pi-compaction-model/pull/1): restore cumulative file-operation lists before falling back to Pi's active model. This concerns file lists in compaction summaries, not loss of files on disk.

Kit-specific changes: source-install documentation and private package metadata; aligning the lockfile's peer range with the inherited manifest; and omitting deleted (`null`) authentication headers before calling `compact()`, matching Pi 0.85.1's native bridge, with a regression test. A root `index.ts` re-exports the implementation so Pi's compact extension list shows the containing directory name rather than `src`. The original compaction routing, file-list restoration, tests, and `compactionModel` configuration are retained. This directory is not separately published to npm; `npm:pi-compaction-model` installs the upstream package, not this derivative.

## Install from source

Requires Pi with the APIs used by this extension (upstream declares `>=0.80.7`). See [Development](#development) for the verification summary and detailed record; the declared minimum is not a tested compatibility matrix. Runtime dependencies are supplied by Pi; Bun is needed only for development. The commands below assume a POSIX shell.

Review this directory, then copy it from a checkout:

```bash
git clone https://github.com/MDGChamomile/pi-agent-kit.git
mkdir -p ~/.pi/agent/extensions
cp -R pi-agent-kit/live/extensions/pi-compaction-model ~/.pi/agent/extensions/
```

Copy only into a destination that does not already exist; do not overwrite another installation. Keep `package.json`, `index.ts`, `src/`, and `LICENSE` together: the `pi.extensions` manifest points to the root `index.ts`, which forwards to `src/index.ts`. No build or dependency installation is required for runtime use.

If upstream is already installed, remove its Pi package registration with `pi remove npm:pi-compaction-model` as part of the transition before loading this copy. Also check for any other copies registered through settings or symlinks. Do not load both versions: both handle the same compaction hook.

Restart Pi after installation, or use `/reload`.

## Configure

Add `compactionModel` to `~/.pi/agent/settings.json`:

```json
{
  "compactionModel": {
    "model": "openai-codex/gpt-5.6-terra",
    "thinkingLevel": "medium"
  }
}
```

`model` must be a model known to Pi in `provider/model` form.

Supported thinking levels are:

```text
off, minimal, low, medium, high, xhigh, max
```

Omit `thinkingLevel` to use the provider default.

### Select which compactions to route

By default the configured model handles all native compaction reasons:

- `manual` — `/compact`
- `threshold` — automatic context-threshold compaction
- `overflow` — overflow recovery before retry

Use `reasons` to handle only a subset:

```json
{
  "compactionModel": {
    "model": "google/gemini-2.5-flash",
    "thinkingLevel": "low",
    "reasons": ["threshold", "overflow"]
  }
}
```

An empty `reasons` array disables routing without removing the configuration. You can also use `"enabled": false`, or set `"compactionModel": false` in trusted project settings.

### Project overrides

A trusted project's `.pi/settings.json` can override individual global fields:

```json
{
  "compactionModel": {
    "model": "anthropic/claude-sonnet-4-5"
  }
}
```

Project fields are shallow-merged over the global `compactionModel` object. Untrusted project settings are ignored.

## Coexisting with other compaction extensions

Multiple extensions can handle `session_before_compact`, and the last extension that returns a compaction result wins. Avoid configuring two extensions for the same reason.

For example, to use Smart Compact manually and this extension only for automatic native compaction:

```json
{
  "smartCompact": {
    "autoTrigger": false
  },
  "compactionModel": {
    "model": "openai-codex/gpt-5.6-terra",
    "thinkingLevel": "medium",
    "reasons": ["threshold", "overflow"]
  }
}
```

The resulting routing is:

| Event | Handler |
|---|---|
| `/smart-compact` | Smart Compact |
| `/compact` | Pi native compaction with the active model |
| Automatic threshold | Pi native compaction algorithm with the configured model |
| Overflow recovery | Pi native compaction algorithm with the configured model |
| Configured-model failure | Control returns to Pi's native handling path |

## OpenRouter attribution

For OpenRouter models, the extension adds the same app-attribution headers as Pi's normal request path before calling the exported `compact()` function. This also applies to custom providers whose base URL is on `openrouter.ai`. Attribution is sent only when Pi's install telemetry is enabled through `enableInstallTelemetry` or `PI_TELEMETRY`; explicitly configured request headers take precedence.

## Failure behavior

### Configuration errors

Configuration fields recover independently:

| Condition | Behavior |
| --- | --- |
| Configured section has a missing or empty `model`, or `model` is not in `provider/model` form | Warns, does not use a dedicated model, and returns control to Pi's native handling path |
| Model not found | Warns and returns control to Pi's native handling path |
| Authentication unavailable | Warns and returns control to Pi's native handling path |
| Invalid `thinkingLevel` | Keeps the dedicated model, warns, and omits the thinking setting so the provider default applies |
| Invalid `reasons` | Keeps the dedicated model, warns, and handles `manual`, `threshold`, and `overflow` |

An empty valid `reasons` array is not an error; it disables dedicated-model routing. Pi currently resolves authentication for the active conversation model before firing the compaction extension hook. Consequently, the active model must also have valid authentication even when a dedicated compaction model is configured.

### Request failures and cancellation

If a dedicated-model request fails while its cancellation signal is not aborted, the extension warns and returns no result, allowing Pi's native handling path to continue. If the error is caught after the signal is aborted, the extension suppresses the warning and likewise returns no result.

Returning no result does not mean that the extension starts a request with the active model. In particular, after cancellation it does not guarantee that Pi will perform another compaction request.

## Development

From this directory, with Bun 1.3.14:

```bash
bun install --frozen-lockfile
bun run check
```

The `live-validation` workflow runs the same commands. A fresh frozen-lockfile installation against the inherited Pi 0.80.7 dependency passed typechecking and all 13 tests; separate Pi 0.85.1 checks also passed typechecking, tests, loader registration, and bounded dedicated-model/fallback smoke scenarios.

These results do not establish compatibility with every provider or failure mode. Offline checks make no model requests, while live compaction sends session content to the configured provider and can incur usage charges. See [the development and verification record](DEVELOPMENT.md) for environments, harness details, request counts, limitations, and source-only evidence.

## License

[MIT](LICENSE), Copyright (c) 2026 JMHSV.
