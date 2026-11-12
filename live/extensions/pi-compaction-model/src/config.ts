import {
  getAgentDir,
  SettingsManager,
  type ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import { warn } from "./warnings.js";

export const THINKING_LEVELS = [
  "off",
  "minimal",
  "low",
  "medium",
  "high",
  "xhigh",
  "max",
] as const;
export type ThinkingLevel = (typeof THINKING_LEVELS)[number];

export interface CompactionModelConfig {
  model: string;
  thinkingLevel?: ThinkingLevel;
}

type UnknownRecord = Record<string, unknown>;
type Warn = (message: string) => void;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseThinkingLevel(value: unknown, onWarning: Warn): ThinkingLevel | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value === "string" && (THINKING_LEVELS as readonly string[]).includes(value)) {
    return value as ThinkingLevel;
  }
  onWarning(`Invalid thinkingLevel '${String(value)}'; omitting the thinking level.`);
  return undefined;
}

export function resolveConfig(
  settings: unknown,
  onWarning: Warn = (message) => console.warn(`[pi-compaction-model] ${message}`),
): CompactionModelConfig | null {
  const raw = isRecord(settings) ? settings.compactionModel : undefined;
  if (raw === undefined) return null;

  if (!isRecord(raw) || typeof raw.model !== "string" || !raw.model.trim()) {
    onWarning("compactionModel.model must be a non-empty provider/model string; using Pi's active model.");
    return null;
  }

  return {
    model: raw.model.trim(),
    thinkingLevel: parseThinkingLevel(raw.thinkingLevel, onWarning),
  };
}

export function createSettings(ctx: ExtensionContext): SettingsManager {
  return SettingsManager.create(ctx.cwd, getAgentDir(), {
    projectTrusted: ctx.isProjectTrusted(),
  });
}

export function loadConfig(
  ctx: ExtensionContext,
  settings: SettingsManager,
): CompactionModelConfig | null {
  return resolveConfig(settings.getGlobalSettings(), (message) => warn(ctx, message));
}

/** Match Pi's telemetry gate for provider app-attribution headers. */
export function isInstallTelemetryEnabled(
  settings: { getEnableInstallTelemetry(): boolean },
  telemetryEnv: string | undefined = process.env.PI_TELEMETRY,
): boolean {
  if (telemetryEnv === undefined) return settings.getEnableInstallTelemetry();
  return ["1", "true", "yes"].includes(telemetryEnv.toLowerCase());
}
