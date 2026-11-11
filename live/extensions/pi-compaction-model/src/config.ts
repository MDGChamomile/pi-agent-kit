import {
  getAgentDir,
  SettingsManager,
  type ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import { warn } from "./warnings.js";

export const COMPACTION_REASONS = ["manual", "threshold", "overflow"] as const;
export type CompactionReason = (typeof COMPACTION_REASONS)[number];

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
  reasons: CompactionReason[];
}

type UnknownRecord = Record<string, unknown>;
type Warn = (message: string) => void;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function section(settings: unknown): unknown {
  return isRecord(settings) ? settings.compactionModel : undefined;
}

function parseThinkingLevel(value: unknown, onWarning: Warn): ThinkingLevel | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value === "string" && (THINKING_LEVELS as readonly string[]).includes(value)) {
    return value as ThinkingLevel;
  }
  onWarning(`Invalid thinkingLevel '${String(value)}'; omitting the thinking level.`);
  return undefined;
}

function parseReasons(value: unknown, onWarning: Warn): CompactionReason[] {
  if (value === undefined) return [...COMPACTION_REASONS];
  if (
    Array.isArray(value) &&
    value.every(
      (reason) =>
        typeof reason === "string" &&
        (COMPACTION_REASONS as readonly string[]).includes(reason),
    )
  ) {
    return [...new Set(value)] as CompactionReason[];
  }
  onWarning("reasons must contain only manual, threshold, or overflow; handling all reasons.");
  return [...COMPACTION_REASONS];
}

export function resolveConfig(
  globalSettings: unknown,
  projectSettings: unknown,
  onWarning: Warn = (message) => console.warn(`[pi-compaction-model] ${message}`),
): CompactionModelConfig | null {
  const globalSection = section(globalSettings);
  const projectSection = section(projectSettings);

  if (projectSection === false) return null;
  if (globalSection === false && projectSection === undefined) return null;

  const raw: UnknownRecord = {
    ...(isRecord(globalSection) ? globalSection : {}),
    ...(isRecord(projectSection) ? projectSection : {}),
  };

  if (raw.enabled === false) return null;

  if (typeof raw.model !== "string" || !raw.model.trim()) {
    if (globalSection !== undefined || projectSection !== undefined) {
      onWarning("compactionModel.model must be a non-empty provider/model string; using Pi's active model.");
    }
    return null;
  }

  return {
    model: raw.model.trim(),
    thinkingLevel: parseThinkingLevel(raw.thinkingLevel, onWarning),
    reasons: parseReasons(raw.reasons, onWarning),
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
  return resolveConfig(
    settings.getGlobalSettings(),
    ctx.isProjectTrusted() ? settings.getProjectSettings() : undefined,
    (message) => warn(ctx, message),
  );
}

/** Match Pi's telemetry gate for provider app-attribution headers. */
export function isInstallTelemetryEnabled(
  settings: { getEnableInstallTelemetry(): boolean },
  telemetryEnv: string | undefined = process.env.PI_TELEMETRY,
): boolean {
  if (telemetryEnv === undefined) return settings.getEnableInstallTelemetry();
  return ["1", "true", "yes"].includes(telemetryEnv.toLowerCase());
}
