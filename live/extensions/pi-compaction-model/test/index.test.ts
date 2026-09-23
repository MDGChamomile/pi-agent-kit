import { beforeAll, beforeEach, describe, expect, mock, test } from "bun:test";

let config: { model: string; reasons: string[]; thinkingLevel?: string } | null;
let compactImplementation: (...args: any[]) => Promise<any>;
let telemetryEnabled: boolean;
let sleepImplementation: (...args: any[]) => Promise<any>;
const settings = {};

mock.module("node:timers/promises", () => ({
  setTimeout: (...args: any[]) => sleepImplementation(...args),
}));

mock.module("@earendil-works/pi-coding-agent", () => ({
  compact: (...args: any[]) => compactImplementation(...args),
}));

mock.module("../src/config.js", () => ({
  COMPACTION_REASONS: ["manual", "threshold", "overflow"],
  THINKING_LEVELS: ["off", "minimal", "low", "medium", "high", "xhigh", "max"],
  createSettings: () => settings,
  isInstallTelemetryEnabled: () => telemetryEnabled,
  loadConfig: () => config,
  parseModelReference: (reference: string) => {
    const separator = reference.indexOf("/");
    if (separator <= 0 || separator === reference.length - 1) return null;
    return { provider: reference.slice(0, separator), modelId: reference.slice(separator + 1) };
  },
  resolveConfig: () => null,
}));

let compactionModel: any;

beforeAll(async () => {
  compactionModel = (await import("../index.js")).default;
});

beforeEach(() => {
  config = { model: "provider/model", reasons: ["manual", "threshold", "overflow"] };
  compactImplementation = async () => ({ summary: "compacted" });
  telemetryEnabled = true;
  sleepImplementation = async () => {};
});

function harness(options: {
  reason?: string;
  findModel?: boolean;
  model?: { provider: string; id: string; baseUrl: string };
  auth?: { ok: boolean; error?: string; apiKey?: string; baseUrl?: unknown; headers?: Record<string, string | null>; env?: Record<string, string> };
} = {}) {
  let handler: any;
  const model = options.model ?? {
    provider: "provider",
    id: "model",
    baseUrl: "https://api.example.com",
  };
  const preparation = {
    fileOps: {
      read: new Set(["current-read.ts"]),
      edited: new Set(["current-edit.ts"]),
    },
  };
  const event = {
    reason: options.reason ?? "manual",
    preparation,
    branchEntries: [
      {
        type: "compaction",
        details: {
          readFiles: ["previous-read.ts", "previous-read.ts", "current-read.ts"],
          modifiedFiles: ["previous-edit.ts", "previous-edit.ts", "current-edit.ts"],
        },
      },
    ],
    customInstructions: undefined,
    signal: new AbortController().signal,
  };
  const ctx = {
    modelRegistry: {
      find: () => options.findModel === false ? undefined : model,
      getApiKeyAndHeaders: async () => options.auth ?? { ok: true, apiKey: "key" },
    },
  };
  compactionModel({ on: (_name: string, registered: any) => { handler = registered; } });
  return { handler, event, ctx, preparation, model };
}

function expectRestored(preparation: { fileOps: { read: Set<string>; edited: Set<string> } }): void {
  expect([...preparation.fileOps.read]).toEqual(["current-read.ts", "previous-read.ts"]);
  expect([...preparation.fileOps.edited]).toEqual(["current-edit.ts", "previous-edit.ts"]);
}

describe("session_before_compact", () => {
  test("restores previous file operations before excluded-reason fallback", async () => {
    config = { model: "provider/model", reasons: ["manual"] };
    const state = harness({ reason: "threshold" });

    expect(await state.handler(state.event, state.ctx)).toBeUndefined();
    expectRestored(state.preparation);
  });

  test("restores previous file operations before model lookup fallback", async () => {
    const state = harness({ findModel: false });

    expect(await state.handler(state.event, state.ctx)).toBeUndefined();
    expectRestored(state.preparation);
  });

  test("restores previous file operations before authentication fallback", async () => {
    const state = harness({ auth: { ok: false, error: "missing credentials" } });

    expect(await state.handler(state.event, state.ctx)).toBeUndefined();
    expectRestored(state.preparation);
  });

  test("passes restored, deduplicated file operations to the dedicated model", async () => {
    const state = harness();
    let compactPreparation: unknown;
    compactImplementation = async (preparation) => {
      compactPreparation = preparation;
      return { summary: "dedicated" };
    };

    expect(await state.handler(state.event, state.ctx)).toEqual({
      compaction: { summary: "dedicated" },
    });
    expect(compactPreparation).toBe(state.preparation);
    expectRestored(state.preparation);
  });

  test("omits deleted headers and forwards authentication and compaction options", async () => {
    config = { model: "provider/model", reasons: ["manual"], thinkingLevel: "low" };
    const state = harness({
      auth: {
        ok: true,
        apiKey: "test-key",
        headers: { "x-test": "retained", "x-deleted": null },
        env: { TEST_ENV: "test-value" },
      },
    });
    let received: unknown[] = [];
    compactImplementation = async (...args) => {
      received = args;
      return { summary: "dedicated" };
    };

    expect(await state.handler(state.event, state.ctx)).toEqual({ compaction: { summary: "dedicated" } });
    expect(received).toEqual([
      state.preparation, state.model, "test-key", { "x-test": "retained" },
      state.event.customInstructions, state.event.signal, "low", undefined,
      { TEST_ENV: "test-value" },
    ]);
    await expect(state.ctx.modelRegistry.getApiKeyAndHeaders()).resolves.toEqual({
      ok: true,
      apiKey: "test-key",
      headers: { "x-test": "retained", "x-deleted": null },
      env: { TEST_ENV: "test-value" },
    });
  });

  for (const reason of ["manual", "threshold", "overflow"]) {
    test(`uses the credential endpoint for ${reason} without mutating the registry`, async () => {
      const state = harness({ reason, auth: {
        ok: true, apiKey: "test-key", baseUrl: "https://credential.example.com",
        headers: { retained: "yes", deleted: null }, env: { TEST_ENV: "value" },
      } });
      const original = { ...state.model };
      Object.freeze(state.model);
      compactImplementation = async (...args) => {
        expect(args[1]).toEqual({ ...original, baseUrl: "https://credential.example.com" });
        expect(args[1]).not.toBe(state.model);
        expect(args[2]).toBe("test-key");
        expect(args[3]).toEqual({ retained: "yes" });
        expect(args[5]).toBe(state.event.signal);
        expect(args[8]).toEqual({ TEST_ENV: "value" });
        return { summary: "dedicated" };
      };
      expect(await state.handler(state.event, state.ctx)).toEqual({ compaction: { summary: "dedicated" } });
      expect(state.model).toEqual(original);
    });
  }

  for (const baseUrl of [undefined, "", null, 42]) {
    test(`keeps the registry model for absent or invalid endpoint ${baseUrl}`, async () => {
      const state = harness({ auth: { ok: true, apiKey: "key", baseUrl } });
      compactImplementation = async (_preparation, model) => {
        expect(model).toBe(state.model);
        return { summary: "dedicated" };
      };
      expect(await state.handler(state.event, state.ctx)).toEqual({ compaction: { summary: "dedicated" } });
    });
  }

  test("uses the credential endpoint for attribution in both directions", async () => {
    for (const toOpenRouter of [true, false]) {
      const state = harness({
        model: { provider: "custom", id: "model", baseUrl: toOpenRouter
          ? "https://api.example.com" : "https://openrouter.ai/api/v1" },
        auth: { ok: true, apiKey: "key", baseUrl: toOpenRouter
          ? "https://openrouter.ai/api/v1" : "https://api.example.com" },
      });
      let headers: any;
      compactImplementation = async (_preparation, _model, _key, received) => {
        headers = received;
        return { summary: "dedicated" };
      };
      await state.handler(state.event, state.ctx);
      expect(headers?.["HTTP-Referer"]).toBe(toOpenRouter ? "https://pi.dev" : undefined);
    }
  });

  test("adds Pi attribution for an OpenRouter compaction request", async () => {
    config = { model: "openrouter/model", reasons: ["manual"] };
    const state = harness({
      model: {
        provider: "openrouter",
        id: "model",
        baseUrl: "https://openrouter.ai/api/v1",
      },
      auth: {
        ok: true,
        apiKey: "test-key",
        headers: { "HTTP-Referer": "https://caller.example", "x-deleted": null },
      },
    });
    let receivedHeaders: unknown;
    compactImplementation = async (_preparation, _model, _apiKey, headers) => {
      receivedHeaders = headers;
      return { summary: "dedicated" };
    };

    await state.handler(state.event, state.ctx);
    expect(receivedHeaders).toEqual({
      "HTTP-Referer": "https://caller.example",
      "X-OpenRouter-Title": "pi",
      "X-OpenRouter-Categories": "cli-agent",
    });
  });

  test("detects OpenRouter by base URL for a custom provider", async () => {
    const state = harness({
      model: {
        provider: "custom",
        id: "model",
        baseUrl: "https://openrouter.ai/api/v1",
      },
    });
    let receivedHeaders: unknown;
    compactImplementation = async (_preparation, _model, _apiKey, headers) => {
      receivedHeaders = headers;
      return { summary: "dedicated" };
    };

    await state.handler(state.event, state.ctx);
    expect(receivedHeaders).toEqual({
      "HTTP-Referer": "https://pi.dev",
      "X-OpenRouter-Title": "pi",
      "X-OpenRouter-Categories": "cli-agent",
    });
  });

  test("does not add attribution for other providers or when telemetry is disabled", async () => {
    const otherProvider = harness({
      auth: { ok: true, apiKey: "test-key", headers: { "x-test": "retained" } },
    });
    let receivedHeaders: unknown;
    compactImplementation = async (_preparation, _model, _apiKey, headers) => {
      receivedHeaders = headers;
      return { summary: "dedicated" };
    };
    await otherProvider.handler(otherProvider.event, otherProvider.ctx);
    expect(receivedHeaders).toEqual({ "x-test": "retained" });

    telemetryEnabled = false;
    config = { model: "openrouter/model", reasons: ["manual"] };
    const telemetryOff = harness({
      model: {
        provider: "openrouter",
        id: "model",
        baseUrl: "https://openrouter.ai/api/v1",
      },
      auth: { ok: true, apiKey: "test-key", headers: { "x-test": "retained" } },
    });
    await telemetryOff.handler(telemetryOff.event, telemetryOff.ctx);
    expect(receivedHeaders).toEqual({ "x-test": "retained" });
  });

  for (const reason of ["manual", "threshold", "overflow"]) {
    test(`retries a transient ${reason} failure once with the same arguments`, async () => {
      const state = harness({ reason });
      const calls: any[][] = [];
      const waits: any[][] = [];
      sleepImplementation = async (...args) => { waits.push(args); };
      compactImplementation = async (...args) => {
        calls.push(args);
        if (calls.length === 1) throw new Error("Summarization failed: 503 Service unavailable");
        return { summary: "recovered" };
      };
      expect(await state.handler(state.event, state.ctx)).toEqual({ compaction: { summary: "recovered" } });
      expect(calls).toHaveLength(2);
      expect(calls[1]).toEqual(calls[0]);
      expect(calls[0]).toHaveLength(9); // Do not enable a nested native retry loop.
      expect(waits).toEqual([[1000, undefined, { signal: state.event.signal }]]);
      expectRestored(state.preparation);
    });
  }

  test("falls back after the second transient failure without another wait", async () => {
    const state = harness();
    let calls = 0;
    let waits = 0;
    sleepImplementation = async () => { waits++; };
    compactImplementation = async () => { calls++; throw new Error("terminated"); };
    expect(await state.handler(state.event, state.ctx)).toBeUndefined();
    expect(calls).toBe(2);
    expect(waits).toBe(1);
    expectRestored(state.preparation);
  });

  test("does not retry success or deterministic and unknown failures", async () => {
    for (const message of [undefined, "401 Unauthorized", "invalid request: 503 tokens",
      "429 insufficient_quota", "429 billing limit", "context window exceeded",
      "Server requested 120s retry delay (max: 60s)", "unknown failure"]) {
      const state = harness();
      let calls = 0;
      let waits = 0;
      sleepImplementation = async () => { waits++; };
      compactImplementation = async () => {
        calls++;
        if (message) throw new Error(message);
        return { summary: "ok" };
      };
      const result = await state.handler(state.event, state.ctx);
      expect(result).toEqual(message ? undefined : { compaction: { summary: "ok" } });
      expect(calls).toBe(1);
      expect(waits).toBe(0);
    }
  });

  test("does not retry authentication or lookup failures", async () => {
    let calls = 0;
    compactImplementation = async () => { calls++; };
    for (const options of [{ findModel: false }, { auth: { ok: false, error: "503 authentication unavailable" } }]) {
      const state = harness(options);
      expect(await state.handler(state.event, state.ctx)).toBeUndefined();
    }
    expect(calls).toBe(0);
  });

  test("cancels before a call, during failure, backoff, or the retry", async () => {
    for (const phase of ["before", "failure", "backoff", "retry", "success"]) {
      const state = harness();
      const controller = new AbortController();
      state.event.signal = controller.signal;
      let calls = 0;
      let waits = 0;
      if (phase === "before") controller.abort();
      sleepImplementation = async () => {
        waits++;
        if (phase === "backoff") controller.abort();
      };
      compactImplementation = async () => {
        calls++;
        if (phase === "failure" || phase === "success" || (phase === "retry" && calls === 2)) controller.abort();
        if (phase === "success") return { summary: "late result" };
        throw new Error("503 Service unavailable");
      };
      expect(await state.handler(state.event, state.ctx)).toEqual({ cancel: true });
      expect(calls).toBe(phase === "before" ? 0 : phase === "retry" ? 2 : 1);
      expect(waits).toBe(phase === "backoff" || phase === "retry" ? 1 : 0);
    }
  });

  test("treats AbortError as cancellation even without an aborted signal", async () => {
    const state = harness();
    let calls = 0;
    compactImplementation = async () => { calls++; throw new DOMException("Aborted", "AbortError"); };
    expect(await state.handler(state.event, state.ctx)).toEqual({ cancel: true });
    expect(calls).toBe(1);
  });

  test("classifies known transient failures conservatively", async () => {
    const { isTransientCompactionError } = await import("../src/retry.js");
    for (const message of ["429 Too many requests", "502 Bad Gateway", "fetch failed",
      "ECONNRESET", "ETIMEDOUT", "EAI_AGAIN", "socket hang up", "terminated",
      "stream ended before a terminal response event", "request timed out"]) {
      expect(isTransientCompactionError(new Error(message))).toBe(true);
    }
    for (const error of ["503", null, new Error("model not found"), new Error("invalid api key: rate limit"),
      new Error("429 FreeUsageLimitError"), new Error("billing service unavailable")]) {
      expect(isTransientCompactionError(error)).toBe(false);
    }
  });

  test("keeps restored file operations when dedicated compaction throws", async () => {
    const state = harness();
    compactImplementation = async (preparation) => {
      expectRestored(preparation);
      throw new Error("provider failed");
    };

    expect(await state.handler(state.event, state.ctx)).toBeUndefined();
    expectRestored(state.preparation);
  });
});
