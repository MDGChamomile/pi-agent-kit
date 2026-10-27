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

Kit-specific changes since that revision, such as source-install documentation, private package metadata, and summarization through Pi's model registry, are recorded in this repository's history. A root `index.ts` re-exports the implementation so Pi's compact extension list shows the containing directory name rather than `src`. The `compactionModel` configuration format and file-list restoration are retained. This directory is not separately published to npm; `npm:pi-compaction-model` installs the upstream package, not this derivative.

## Install from source

Requires Pi 1.0.0 or later. See [Development](#development) for the tested versions; this is not a full compatibility matrix. Runtime dependencies are supplied by Pi; Bun is needed only for development. The commands below assume a POSIX shell.

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
    "model": "provider/summary-model",
    "thinkingLevel": "medium"
  }
}
```

`model` must be a model known to Pi in `provider/model` form; `pi --list-models` shows the available IDs. Summarization uses Pi's model-registry stream path, including extension-registered providers and provider-specific authentication.

Supported thinking levels are:

```text
off, minimal, low, medium, high, xhigh, max
```

Omitting `thinkingLevel` leaves it unset; it does not inherit the active conversation's thinking level. Pi's provider adapters may interpret an unset level as off or the model's off mapping. Set it explicitly when a particular level is required.

### Select which compactions to route

By default the configured model handles all native compaction reasons:

- `manual` — `/compact`
- `threshold` — automatic context-threshold compaction
- `overflow` — overflow recovery before retry

Use `reasons` to handle only a subset:

```json
{
  "compactionModel": {
    "model": "provider/fast-model",
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
    "model": "provider/project-model"
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
    "model": "provider/summary-model",
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
| Configured-model failure | Retries transient request failures according to Pi's `retry` settings, then returns control to Pi's native handling path |

## OpenRouter attribution

Credential-specific base URLs returned by Pi's authentication resolver override the registry model's endpoint for the compaction request and attribution check. The shared registry model is not modified; when authentication supplies no non-empty string URL, the registry endpoint is retained.

For OpenRouter models, the extension adds the same app-attribution headers as Pi's normal request path before calling the exported `compact()` function. This also applies to custom providers whose base URL is on `openrouter.ai`. Attribution is sent only when Pi's install telemetry is enabled through `enableInstallTelemetry` or `PI_TELEMETRY`; explicitly configured request headers take precedence.

## Failure behavior

Configuration and request warnings use Pi's warning notifications when `ctx.hasUI` is true (interactive and supported RPC clients). Without a UI, they use `console.warn` on stderr. Cancellation and successful requests, including a successful retry, do not produce fallback warnings.

### Configuration errors

Configuration fields recover independently:

| Condition | Behavior |
| --- | --- |
| Configured section has a missing or empty `model`, or `model` is not in `provider/model` form | Warns, does not use a dedicated model, and returns control to Pi's native handling path |
| Model not found | Warns and returns control to Pi's native handling path |
| Authentication unavailable | Warns and returns control to Pi's native handling path |
| Invalid `thinkingLevel` | Keeps the dedicated model, warns, and omits the thinking setting |
| Invalid `reasons` | Keeps the dedicated model, warns, and handles `manual`, `threshold`, and `overflow` |

An empty valid `reasons` array is not an error; it disables dedicated-model routing. The dedicated model needs its own valid authentication. If Pi falls back to native compaction, the active conversation model's normal authentication requirements apply.

### Request failures and cancellation

The extension passes Pi's `retry` settings to native `compact()`, the same policy Pi applies to its own compaction. Each summarization request is retried for errors Pi classifies as transient, such as a 503 response, temporary rate limiting, or a dropped stream. Retries follow `retry.maxRetries` and exponential backoff from `retry.baseDelayMs`, capped by `retry.maxAgentDelayMs`; `retry.enabled: false` disables them. Deterministic failures such as authentication, invalid requests, or quota/billing exhaustion are not retried. A split-turn compaction retries only its failed request. Retry progress is not shown in the UI, and retrying can add latency and provider usage.

A failure that remains after those retries returns control to Pi's native handling path with a warning. Model lookup and authentication-resolution failures are not retried.

Cancellation during a request or retry wait returns `{ cancel: true }` without a fallback warning. An `AbortError` is also treated as cancellation. Returning no result on other failures hands control back to Pi; the extension does not itself start an active-model request.

## Development

From this directory, with Bun 1.3.14:

```bash
bun install --frozen-lockfile
bun run check
```

The `live-validation` workflow runs these checks against the pinned minimum, Pi 1.0.0, and `pi-latest-compatibility` runs them weekly against Pi's latest release. Offline checks use synthetic data and make no live model requests. The provider-routing tests exercise real Pi compaction, model-registry dispatch and authentication with an in-memory credential store and stubbed transport, including a custom API and Cloudflare Gateway header deletions. Live compaction sends session content to the configured provider and can incur usage charges.

## License

[MIT](LICENSE), Copyright (c) 2026 JMHSV.
