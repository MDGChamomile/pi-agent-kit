import { closeSync, existsSync, openSync, readFileSync, readSync, readdirSync, statSync } from "node:fs";
import { join, basename } from "node:path";
import type { Theme } from "@earendil-works/pi-coding-agent";
import type { Component } from "@earendil-works/pi-tui";
import { truncateToWidth as tuiTruncateToWidth, visibleWidth } from "@earendil-works/pi-tui";
import { getAgentPath, getAgentSessionDirs, getHomeDir } from "./paths.ts";

export interface RecentSession {
  name: string;
  timeAgo: string;
}

export interface LoadedCounts {
  contextFiles: number;
  extensions: number;
  skills: number;
  promptTemplates: number;
}

function formatTokens(tokens: number): string {
  if (tokens < 1000) return tokens.toString();
  if (tokens < 10000) return `${(tokens / 1000).toFixed(1)}k`;
  if (tokens < 1000000) return `${Math.round(tokens / 1000)}k`;
  return `${(tokens / 1000000).toFixed(tokens < 10000000 ? 1 : 0)}M`;
}

// ═══════════════════════════════════════════════════════════════════════════
// Shared rendering utilities
// ═══════════════════════════════════════════════════════════════════════════

const PI_LOGO = [
  "██████████    ",
  "████  ████    ",
  "████  ████    ",
  "████████  ████",
  "████      ████",
  "████      ████",
];

const SESSION_HEADER_READ_BYTES = 8192;

function centerText(text: string, width: number): string {
  const visLen = visibleWidth(text);
  if (visLen > width) return tuiTruncateToWidth(text, width, "…");
  if (visLen === width) return text;
  const leftPad = Math.floor((width - visLen) / 2);
  const rightPad = width - visLen - leftPad;
  return " ".repeat(leftPad) + text + " ".repeat(rightPad);
}

function fitToWidth(str: string, width: number): string {
  const visLen = visibleWidth(str);
  if (visLen > width) return tuiTruncateToWidth(str, width, "…");
  return str + " ".repeat(width - visLen);
}

interface WelcomeData {
  theme: Theme;
  modelName: string;
  providerName: string;
  recentSessions: RecentSession[];
  loadedCounts: LoadedCounts;
  initialContextTokens: number | null;
}

function buildLeftColumn(data: WelcomeData, colWidth: number): string[] {
  const { theme } = data;
  const logoColored = PI_LOGO.map((line) => theme.fg("accent", line));

  return [
    "",
    centerText(theme.bold("Welcome back!"), colWidth),
    "",
    ...logoColored.map((line) => centerText(line, colWidth)),
    "",
    centerText(theme.fg("toolTitle", data.modelName), colWidth),
    centerText(theme.fg("dim", data.providerName), colWidth),
  ];
}

function buildRightColumn(data: WelcomeData, colWidth: number): string[] {
  const { theme } = data;
  const hChar = "─";
  const separator = ` ${theme.fg("dim", hChar.repeat(colWidth - 2))}`;

  const sessionLines: string[] = [];
  if (data.recentSessions.length === 0) {
    sessionLines.push(` ${theme.fg("dim", "No recent sessions")}`);
  } else {
    for (const session of data.recentSessions.slice(0, 3)) {
      sessionLines.push(
        ` ${theme.fg("dim", "• ")}${theme.fg("accent", session.name)}${theme.fg("dim", ` (${session.timeAgo})`)}`,
      );
    }
  }

  const countLines: string[] = [];
  const { contextFiles, extensions, skills, promptTemplates } = data.loadedCounts;
  const itemPrefix = theme.fg("dim", "- ");

  if (contextFiles > 0 || extensions > 0 || skills > 0 || promptTemplates > 0) {
    if (contextFiles > 0) {
      countLines.push(` ${itemPrefix}${theme.fg("success", `${contextFiles}`)} context file${contextFiles !== 1 ? "s" : ""}`);
    }
    if (extensions > 0) {
      countLines.push(` ${itemPrefix}${theme.fg("success", `${extensions}`)} extension${extensions !== 1 ? "s" : ""}`);
    }
    if (skills > 0) {
      countLines.push(` ${itemPrefix}${theme.fg("success", `${skills}`)} skill${skills !== 1 ? "s" : ""}`);
    }
    if (promptTemplates > 0) {
      countLines.push(` ${itemPrefix}${theme.fg("success", `${promptTemplates}`)} prompt template${promptTemplates !== 1 ? "s" : ""}`);
    }
  } else {
    countLines.push(` ${theme.fg("dim", "No extensions loaded")}`);
  }

  if (
    data.initialContextTokens !== null
    && Number.isFinite(data.initialContextTokens)
    && data.initialContextTokens > 0
  ) {
    countLines.push(` ${itemPrefix}${theme.fg("success", `≈ ${formatTokens(data.initialContextTokens)}`)} initial prompt tokens`);
  }

  const heading = (text: string) => theme.bold(theme.fg("accent", text));
  return [
    ` ${heading("Tips")}`,
    ` ${theme.fg("dim", "/")} for commands`,
    ` ${theme.fg("dim", "!")} to run bash`,
    ` ${theme.fg("dim", "Shift+Tab")} cycle thinking`,
    separator,
    ` ${heading("Loaded")}`,
    ...countLines,
    separator,
    ` ${heading("Recent sessions")}`,
    ...sessionLines,
    "",
  ];
}

function renderWelcomeBox(
  data: WelcomeData,
  termWidth: number,
  bottomLine: string,
): string[] {
  const { theme } = data;
  // Minimum width for two-column layout: leftCol(26) + separator(3) + minRightCol(15) = 44
  const minLayoutWidth = 44;
  
  // If terminal is too narrow for the layout, return empty (skip welcome box)
  if (termWidth < minLayoutWidth) {
    return [];
  }
  
  const minWidth = 76;
  const maxWidth = 96;
  // Clamp to termWidth to prevent crash on narrow terminals
  const boxWidth = Math.min(termWidth, Math.max(minWidth, Math.min(termWidth - 2, maxWidth)));
  const leftCol = 26;
  const rightCol = Math.max(1, boxWidth - leftCol - 3); // Ensure rightCol is at least 1
  
  const hChar = "─";
  const v = theme.fg("dim", "│");
  const tl = theme.fg("dim", "╭");
  const tr = theme.fg("dim", "╮");
  const bl = theme.fg("dim", "╰");
  const br = theme.fg("dim", "╯");
  
  const leftLines = buildLeftColumn(data, leftCol);
  const rightLines = buildRightColumn(data, rightCol);
  
  const lines: string[] = [];
  
  // Top border with title
  const title = " pi agent ";
  const titlePrefix = theme.fg("dim", hChar.repeat(3));
  const titleStyled = titlePrefix + theme.fg("toolTitle", title);
  const titleVisLen = 3 + visibleWidth(title);
  const afterTitle = boxWidth - 2 - titleVisLen;
  const afterTitleText = afterTitle > 0 ? theme.fg("dim", hChar.repeat(afterTitle)) : "";
  lines.push(tl + titleStyled + afterTitleText + tr);
  
  // Content rows
  const maxRows = Math.max(leftLines.length, rightLines.length);
  for (let i = 0; i < maxRows; i++) {
    const left = fitToWidth(leftLines[i] ?? "", leftCol);
    const right = fitToWidth(rightLines[i] ?? "", rightCol);
    lines.push(v + left + v + right + v);
  }
  
  // Bottom border
  lines.push(bl + bottomLine + br);
  
  return lines;
}

// ═══════════════════════════════════════════════════════════════════════════
// Welcome Components
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Welcome overlay component for pi agent.
 * Displays a branded splash screen with logo, tips, and loaded counts.
 */
export class WelcomeComponent implements Component {
  private data: WelcomeData;
  private countdown: number = 30;

  constructor(
    theme: Theme,
    modelName: string,
    providerName: string,
    recentSessions: RecentSession[] = [],
    loadedCounts: LoadedCounts = { contextFiles: 0, extensions: 0, skills: 0, promptTemplates: 0 },
    initialContextTokens: number | null = null,
  ) {
    this.data = { theme, modelName, providerName, recentSessions, loadedCounts, initialContextTokens };
  }

  setCountdown(seconds: number): void {
    this.countdown = seconds;
  }

  invalidate(): void {}

  render(termWidth: number): string[] {
    // Minimum width for two-column layout (must match renderWelcomeBox)
    const minLayoutWidth = 44;
    if (termWidth < minLayoutWidth) {
      return [];
    }
    
    const minWidth = 76;
    const maxWidth = 96;
    // Clamp to termWidth to prevent crash on narrow terminals
    const boxWidth = Math.min(termWidth, Math.max(minWidth, Math.min(termWidth - 2, maxWidth)));
    
    // Bottom line with countdown
    const countdownText = ` Press any key to continue (${this.countdown}s) `;
    const countdownStyled = this.data.theme.fg("dim", countdownText);
    const bottomContentWidth = boxWidth - 2;
    const countdownVisLen = visibleWidth(countdownText);
    const leftPad = Math.floor((bottomContentWidth - countdownVisLen) / 2);
    const rightPad = bottomContentWidth - countdownVisLen - leftPad;
    const hChar = "─";
    const bottomLine = this.data.theme.fg("dim", hChar.repeat(Math.max(0, leftPad))) +
      countdownStyled +
      this.data.theme.fg("dim", hChar.repeat(Math.max(0, rightPad)));
    
    return renderWelcomeBox(this.data, termWidth, bottomLine);
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Discovery functions
// ═══════════════════════════════════════════════════════════════════════════

const loggedDiscoveryErrors = new Set<string>();

function logDiscoveryError(scope: string, error: unknown): void {
  if (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    (error as { code?: unknown }).code === "ENOENT"
  ) {
    return;
  }

  const message = error instanceof Error ? error.message : String(error);
  const key = `${scope}:${message}`;
  if (loggedDiscoveryErrors.has(key)) {
    return;
  }

  loggedDiscoveryErrors.add(key);
  if (loggedDiscoveryErrors.size > 500) {
    loggedDiscoveryErrors.clear();
  }

  console.debug(`[powerline-welcome] ${scope}:`, error);
}

/**
 * Discover loaded counts by scanning filesystem.
 */
export function discoverLoadedCounts(): LoadedCounts {
  const homeDir = getHomeDir();
  const cwd = process.cwd();
  
  let contextFiles = 0;
  let extensions = 0;
  let skills = 0;
  let promptTemplates = 0;

  const agentsMdPaths = [
    getAgentPath("AGENTS.md"),
    join(homeDir, ".claude", "AGENTS.md"),
    join(cwd, "AGENTS.md"),
    join(cwd, ".pi", "AGENTS.md"),
    join(cwd, ".claude", "AGENTS.md"),
  ];
  
  for (const path of agentsMdPaths) {
    if (existsSync(path)) contextFiles++;
  }

  const extensionDirs = [
    getAgentPath("extensions"),
    join(cwd, "extensions"),
    join(cwd, ".pi", "extensions"),
  ];

  const countedExtensions = new Set<string>();

  const settingsPaths = [
    getAgentPath("settings.json"),
    join(cwd, ".pi", "settings.json"),
  ];

  for (const settingsPath of settingsPaths) {
    if (!existsSync(settingsPath)) {
      continue;
    }

    try {
      const settings = JSON.parse(readFileSync(settingsPath, "utf-8"));
      let packages: unknown = null;
      if (typeof settings === "object" && settings !== null && !Array.isArray(settings)) {
        packages = (settings as { packages?: unknown }).packages;
      }

      if (Array.isArray(packages)) {
        for (const pkg of packages) {
          let source: unknown = null;
          let extensionsFilter: unknown = null;

          if (typeof pkg === "string") {
            source = pkg;
          } else if (typeof pkg === "object" && pkg !== null && !Array.isArray(pkg)) {
            source = (pkg as { source?: unknown }).source;
            extensionsFilter = (pkg as { extensions?: unknown }).extensions;
          }

          if (typeof source !== "string") {
            continue;
          }

          const normalizedSource = source.trim();
          if (!normalizedSource.startsWith("npm:")) {
            continue;
          }

          if (Array.isArray(extensionsFilter) && extensionsFilter.length === 0) {
            continue;
          }

          const body = normalizedSource.slice(4);
          const versionIndex = body.lastIndexOf("@");
          const name = versionIndex > 0 ? body.slice(0, versionIndex) : body;
          if (!name || countedExtensions.has(name)) {
            continue;
          }

          countedExtensions.add(name);
          extensions++;
        }
      }
    } catch (error) {
      logDiscoveryError(`Failed to read settings at ${settingsPath}`, error);
    }
  }

  for (const dir of extensionDirs) {
    if (existsSync(dir)) {
      try {
        const entries = readdirSync(dir);
        for (const entry of entries) {
          const entryPath = join(dir, entry);

          try {
            const stats = statSync(entryPath);

            if (stats.isDirectory()) {
              if (
                existsSync(join(entryPath, "index.ts")) ||
                existsSync(join(entryPath, "index.js")) ||
                existsSync(join(entryPath, "package.json"))
              ) {
                if (!countedExtensions.has(entry)) {
                  countedExtensions.add(entry);
                  extensions++;
                }
              }
            } else if ((entry.endsWith(".ts") || entry.endsWith(".js")) && !entry.startsWith(".")) {
              const ext = entry.endsWith(".ts") ? ".ts" : ".js";
              const name = basename(entry, ext);
              if (!countedExtensions.has(name)) {
                countedExtensions.add(name);
                extensions++;
              }
            }
          } catch (error) {
            logDiscoveryError(`Failed to inspect extension entry ${entryPath}`, error);
          }
        }
      } catch (error) {
        logDiscoveryError(`Failed to scan extensions dir ${dir}`, error);
      }
    }
  }

  const skillDirs = [
    getAgentPath("skills"),
    join(cwd, ".pi", "skills"),
    join(cwd, "skills"),
  ];
  
  const countedSkills = new Set<string>();
  
  for (const dir of skillDirs) {
    if (existsSync(dir)) {
      try {
        const entries = readdirSync(dir);
        for (const entry of entries) {
          const entryPath = join(dir, entry);
          try {
            if (statSync(entryPath).isDirectory()) {
              if (existsSync(join(entryPath, "SKILL.md"))) {
                if (!countedSkills.has(entry)) {
                  countedSkills.add(entry);
                  skills++;
                }
              }
            }
          } catch (error) {
            logDiscoveryError(`Failed to inspect skill entry ${entryPath}`, error);
          }
        }
      } catch (error) {
        logDiscoveryError(`Failed to scan skills dir ${dir}`, error);
      }
    }
  }

  const templateDirs = [
    getAgentPath("commands"),
    join(homeDir, ".claude", "commands"),
    join(cwd, ".pi", "commands"),
    join(cwd, ".claude", "commands"),
  ];
  
  const countedTemplates = new Set<string>();
  
  function countTemplatesInDir(dir: string) {
    if (!existsSync(dir)) return;
    try {
      const entries = readdirSync(dir);
      for (const entry of entries) {
        const entryPath = join(dir, entry);
        try {
          const stats = statSync(entryPath);
          if (stats.isDirectory()) {
            countTemplatesInDir(entryPath);
          } else if (entry.endsWith(".md")) {
            const name = basename(entry, ".md");
            if (!countedTemplates.has(name)) {
              countedTemplates.add(name);
              promptTemplates++;
            }
          }
        } catch (error) {
          logDiscoveryError(`Failed to inspect prompt template entry ${entryPath}`, error);
        }
      }
    } catch (error) {
      logDiscoveryError(`Failed to scan prompt template dir ${dir}`, error);
    }
  }
  
  for (const dir of templateDirs) {
    countTemplatesInDir(dir);
  }

  return { contextFiles, extensions, skills, promptTemplates };
}

/**
 * Get recent sessions from the sessions directory.
 */
function readSessionHeaderProjectName(filePath: string): string | null {
  let fd: number | null = null;
  try {
    fd = openSync(filePath, "r");
    const buffer = Buffer.alloc(SESSION_HEADER_READ_BYTES);
    const bytesRead = readSync(fd, buffer, 0, buffer.length, 0);
    const firstLine = buffer.toString("utf8", 0, bytesRead).split(/\r?\n/, 1)[0]?.trim();
    if (!firstLine) return null;

    const header: unknown = JSON.parse(firstLine);
    if (typeof header !== "object" || header === null || Array.isArray(header)) return null;

    const cwd = Reflect.get(header, "cwd");
    if (typeof cwd !== "string" || cwd.trim().length === 0) return null;

    return basename(cwd) || cwd;
  } catch {
    return null;
  } finally {
    if (fd !== null) closeSync(fd);
  }
}

function sessionProjectNameFromDirectory(dir: string): string {
  const parentName = basename(dir);
  if (!parentName.startsWith("--")) {
    return parentName;
  }

  const parts = parentName.split("-").filter(p => p);
  return parts[parts.length - 1] || parentName;
}

export function getRecentSessions(maxCount: number = 3): RecentSession[] {
  const sessionsDirs = getAgentSessionDirs();
  
  const sessions: { name: string; mtime: number }[] = [];
  
  function scanDir(dir: string) {
    if (!existsSync(dir)) return;
    try {
      const entries = readdirSync(dir);
      for (const entry of entries) {
        const entryPath = join(dir, entry);
        try {
          const stats = statSync(entryPath);
          if (stats.isDirectory()) {
            scanDir(entryPath);
          } else if (entry.endsWith(".jsonl")) {
            const projectName = readSessionHeaderProjectName(entryPath) ?? sessionProjectNameFromDirectory(dir);
            sessions.push({ name: projectName, mtime: stats.mtimeMs });
          }
        } catch (error) {
          logDiscoveryError(`Failed to inspect session entry ${entryPath}`, error);
        }
      }
    } catch (error) {
      logDiscoveryError(`Failed to scan sessions dir ${dir}`, error);
    }
  }
  
  for (const sessionsDir of sessionsDirs) {
    scanDir(sessionsDir);
  }
  
  if (sessions.length === 0) return [];
  
  sessions.sort((a, b) => b.mtime - a.mtime);
  
  const seen = new Set<string>();
  const uniqueSessions: typeof sessions = [];
  for (const s of sessions) {
    if (!seen.has(s.name)) {
      seen.add(s.name);
      uniqueSessions.push(s);
    }
  }

  const now = Date.now();
  return uniqueSessions.slice(0, maxCount).map(s => ({
    name: s.name.length > 20 ? s.name.slice(0, 17) + "…" : s.name,
    timeAgo: formatTimeAgo(now - s.mtime),
  }));
}

function formatTimeAgo(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  if (minutes > 0) return `${minutes}m ago`;
  return "just now";
}
