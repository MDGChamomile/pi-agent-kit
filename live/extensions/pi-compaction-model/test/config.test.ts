import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import {
  isInstallTelemetryEnabled,
  resolveConfig,
} from "../src/config.js";
import { parseModelReference } from "../src/model-reference.js";

describe("resolveConfig", () => {
  test("returns null when unconfigured", () => {
    expect(resolveConfig({})).toBeNull();
    expect(resolveConfig(undefined)).toBeNull();
  });

  test("reads the model and optional thinking level", () => {
    expect(resolveConfig({ compactionModel: { model: " provider/model " } })).toEqual({
      model: "provider/model",
      thinkingLevel: undefined,
    });
    expect(resolveConfig({ compactionModel: { model: "provider/model", thinkingLevel: "low" } })).toEqual({
      model: "provider/model",
      thinkingLevel: "low",
    });
  });

  test("warns and returns null without a usable model", () => {
    for (const section of [false, [], {}, { model: "" }, { model: 1 }]) {
      const warnings: string[] = [];
      expect(resolveConfig({ compactionModel: section }, (message) => warnings.push(message))).toBeNull();
      expect(warnings).toHaveLength(1);
    }
  });

  test("omits an invalid thinking level with a warning", () => {
    const warnings: string[] = [];
    const config = resolveConfig(
      { compactionModel: { model: "provider/model", thinkingLevel: "extreme" } },
      (message) => warnings.push(message),
    );

    expect(config).toEqual({ model: "provider/model", thinkingLevel: undefined });
    expect(warnings).toHaveLength(1);
  });
});

describe("isInstallTelemetryEnabled", () => {
  const settings = (enabled: boolean) => ({
    getEnableInstallTelemetry: () => enabled,
  });
  let originalTelemetry: string | undefined;
  beforeEach(() => {
    originalTelemetry = process.env.PI_TELEMETRY;
    delete process.env.PI_TELEMETRY;
  });
  afterEach(() => {
    if (originalTelemetry === undefined) delete process.env.PI_TELEMETRY;
    else process.env.PI_TELEMETRY = originalTelemetry;
  });

  test("uses the settings value when PI_TELEMETRY is unset", () => {
    expect(isInstallTelemetryEnabled(settings(true))).toBe(true);
    expect(isInstallTelemetryEnabled(settings(false))).toBe(false);
  });

  test("recognizes truthy PI_TELEMETRY values", () => {
    for (const value of ["1", "true", "TRUE", "yes", "Yes"]) {
      expect(isInstallTelemetryEnabled(settings(false), value)).toBe(true);
    }
  });

  test("treats other PI_TELEMETRY values as disabled", () => {
    for (const value of ["0", "false", "no", ""]) {
      expect(isInstallTelemetryEnabled(settings(true), value)).toBe(false);
    }
  });
});

describe("parseModelReference", () => {
  test("splits only the provider prefix", () => {
    expect(parseModelReference("openrouter/vendor/model")).toEqual({
      provider: "openrouter",
      modelId: "vendor/model",
    });
  });

  test("trims provider and model ID without changing internal slashes", () => {
    expect(parseModelReference(" provider / model ")).toEqual({
      provider: "provider",
      modelId: "model",
    });
    expect(parseModelReference(" openrouter / vendor/model ")).toEqual({
      provider: "openrouter",
      modelId: "vendor/model",
    });
  });

  test("rejects malformed references", () => {
    expect(parseModelReference("model-only")).toBeNull();
    expect(parseModelReference("/model")).toBeNull();
    expect(parseModelReference("provider/")).toBeNull();
    expect(parseModelReference("provider/ ")).toBeNull();
    expect(parseModelReference(" /model")).toBeNull();
  });
});
