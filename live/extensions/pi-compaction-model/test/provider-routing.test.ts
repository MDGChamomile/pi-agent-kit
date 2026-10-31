import { afterEach, beforeAll, beforeEach, expect, mock, test } from "bun:test";
import { ModelRegistry, ModelRuntime, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import {
  createAssistantMessageEventStream, type AssistantMessage, type CredentialStore, type RetryPolicy,
} from "@earendil-works/pi-ai";

// Keep compact(), authentication resolution and provider dispatch real. Only
// settings and the final transport are synthetic; no credentials are read.
let reference: string;
let retry: RetryPolicy;
mock.module("../src/config.js", () => ({
  createSettings: () => ({ getRetrySettings: () => retry }),
  isInstallTelemetryEnabled: () => false,
  loadConfig: () => ({ model: reference, reasons: ["manual"] }),
}));
let extension: (pi: ExtensionAPI) => void;
beforeAll(async () => { extension = (await import("../index.js")).default; });

const originalFetch = globalThis.fetch;
const envNames = ["CLOUDFLARE_API_KEY", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_GATEWAY_ID"] as const;
let originalEnv: Array<string | undefined>;
let requests: Array<{ url: string; headers: Headers }>;
beforeEach(() => {
  originalEnv = envNames.map(name => process.env[name]);
  for (const name of envNames) delete process.env[name];
  retry = { enabled: true, maxRetries: 3, baseDelayMs: 1 };
  requests = [];
  globalThis.fetch = Object.assign(mock(async (input: string | URL | Request, init?: RequestInit) => {
    const url = input instanceof Request ? input.url : String(input);
    requests.push({ url, headers: new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined)) });
    return new Response(JSON.stringify({ error: { message: "synthetic 400 response" } }), {
      status: 400, headers: { "content-type": "application/json" },
    });
  }), { preconnect: mock(() => {}) });
});
afterEach(() => {
  globalThis.fetch = originalFetch;
  envNames.forEach((name, index) => {
    if (originalEnv[index] === undefined) delete process.env[name];
    else process.env[name] = originalEnv[index];
  });
});

async function runtime(storedGatewayKey = false) {
  const credentials: CredentialStore = {
    async read(provider) {
      return storedGatewayKey && provider === "cloudflare-ai-gateway" ? {
        type: "api_key", key: "synthetic-gateway-key",
        env: { CLOUDFLARE_ACCOUNT_ID: "synthetic-account", CLOUDFLARE_GATEWAY_ID: "synthetic-gateway" },
      } : undefined;
    },
    async list() { return []; },
    async modify() { throw new Error("Credential writes are forbidden in this fixture"); },
    async delete() { throw new Error("Credential writes are forbidden in this fixture"); },
  };
  return ModelRuntime.create({ credentials, modelsPath: null, allowModelNetwork: false, refreshOnCreate: false });
}

async function runHook(registry: ModelRegistry, model: string) {
  reference = model;
  let handler: any;
  extension({ on: (_name: string, callback: unknown) => { handler = callback; } } as unknown as ExtensionAPI);
  const notify = mock(() => {});
  const signal = new AbortController().signal;
  const result = await handler({
    reason: "manual", branchEntries: [], signal,
    preparation: {
      messagesToSummarize: [{ role: "user", content: "Synthetic compaction fixture", timestamp: 0 }],
      turnPrefixMessages: [], isSplitTurn: false, firstKeptEntryId: "kept", tokensBefore: 100,
      fileOps: { read: new Set(), edited: new Set(), written: new Set() },
      settings: { enabled: true, reserveTokens: 10, keepRecentTokens: 10 },
    },
  }, { modelRegistry: registry, hasUI: true, ui: { notify } });
  return { result, notify, signal };
}

/** Register a custom API whose responses fail with `failures` error messages before succeeding. */
async function syntheticSummaryProvider(failures: string[] = []) {
  const models = await runtime();
  const signals: Array<AbortSignal | undefined> = [];
  models.registerProvider("synthetic-compaction", {
    api: "synthetic-compaction-api", baseUrl: "https://synthetic.invalid", apiKey: "synthetic-key",
    models: [{ id: "summary", name: "Synthetic summary", reasoning: false, input: ["text"],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 100000, maxTokens: 1000 }],
    streamSimple(model, _context, options) {
      const errorMessage = failures[signals.length];
      signals.push(options?.signal);
      const stream = createAssistantMessageEventStream();
      const message: AssistantMessage = {
        role: "assistant", content: errorMessage ? [] : [{ type: "text", text: "Synthetic summary" }],
        model: model.id, provider: model.provider, api: model.api, timestamp: 0,
        stopReason: errorMessage ? "error" : "stop", errorMessage,
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
      stream.push(errorMessage
        ? { type: "error", reason: "error", error: message }
        : { type: "done", reason: "stop", message });
      stream.end(message);
      return stream;
    },
  });
  return { registry: new ModelRegistry(models), signals };
}

test("real compaction dispatches to an extension-registered custom API", async () => {
  const { registry, signals } = await syntheticSummaryProvider();
  const { result, notify, signal } = await runHook(registry, "synthetic-compaction/summary");
  expect(result?.compaction.summary).toContain("Synthetic summary");
  expect(signals).toEqual([signal]);
  expect(notify).not.toHaveBeenCalled();
  expect(requests).toHaveLength(0);
});

for (const enabled of [true, false]) {
  test(`real compaction follows Pi retry settings for a transient failure: enabled=${enabled}`, async () => {
    retry = { enabled, maxRetries: 1, baseDelayMs: 1 };
    const { registry, signals } = await syntheticSummaryProvider(["503 Service Unavailable"]);
    const { result, notify } = await runHook(registry, "synthetic-compaction/summary");
    if (enabled) {
      expect(result?.compaction.summary).toContain("Synthetic summary");
      expect(notify).not.toHaveBeenCalled();
    } else {
      expect(result).toBeUndefined();
      expect(notify).toHaveBeenCalledTimes(1);
    }
    expect(signals).toHaveLength(enabled ? 2 : 1);
  });
}

test("real compaction falls back after Pi's retry budget is exhausted", async () => {
  retry = { enabled: true, maxRetries: 1, baseDelayMs: 1 };
  const { registry, signals } = await syntheticSummaryProvider(["503 Service Unavailable", "503 Service Unavailable"]);
  const { result, notify } = await runHook(registry, "synthetic-compaction/summary");
  expect(result).toBeUndefined();
  expect(notify).toHaveBeenCalledTimes(1);
  expect(signals).toHaveLength(2);
});

for (const [source, api] of [
  ["env", "openai-completions"], ["env", "anthropic-messages"], ["stored", "openai-completions"],
] as const) {
  test(`real gateway dispatch retains auth-header deletions: ${source}, ${api}`, async () => {
    if (source === "env") {
      process.env.CLOUDFLARE_API_KEY = "synthetic-gateway-key";
      process.env.CLOUDFLARE_ACCOUNT_ID = "synthetic-account";
      process.env.CLOUDFLARE_GATEWAY_ID = "synthetic-gateway";
    }
    const registry = new ModelRegistry(await runtime(source === "stored"));
    const model = registry.getAll().find(model => model.provider === "cloudflare-ai-gateway" && model.api === api);
    expect(model).toBeDefined();
    const { result, notify } = await runHook(registry, `cloudflare-ai-gateway/${model!.id}`);
    // The synthetic deterministic failure must still fall back without retrying.
    expect(result).toBeUndefined();
    expect(notify).toHaveBeenCalledTimes(1);
    expect(requests).toHaveLength(1);
    const request = requests[0]!;
    expect(new URL(request.url).hostname).toBe("gateway.ai.cloudflare.com");
    expect(request.headers.get("cf-aig-authorization")).toBe("Bearer synthetic-gateway-key");
    expect(request.headers.has("authorization")).toBe(false);
    expect(request.headers.has("x-api-key")).toBe(false);
  });
}
