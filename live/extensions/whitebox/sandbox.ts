import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { constants as fsConstants } from "node:fs";
import {
  access,
  chmod,
  lstat,
  mkdtemp,
  opendir,
  readFile,
  readdir,
  realpath,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";

export const BWRAP_PATH = "/usr/bin/bwrap";
export const FLOCK_PATH = "/usr/bin/flock";
export const LOCK_CONFLICT_EXIT_CODE = 75;
export const DEFAULT_TIMEOUT_SECONDS = 120;
export const MAX_TIMEOUT_SECONDS = 900;
export const MAX_CAPTURE_BYTES = 10 * 1024 * 1024;
export const DISPLAY_MAX_BYTES = 44 * 1024;
export const DISPLAY_MAX_LINES = 2_000;
export const TMP_SIZE_BYTES = 1024 * 1024 * 1024;
export const HOME_SIZE_BYTES = 128 * 1024 * 1024;
export const RUN_SIZE_BYTES = 16 * 1024 * 1024;

const TEMP_PREFIX = "pi-whitebox-";
const REQUIRED_USR_TOOLS = [
  "/usr/bin/bash",
  "/usr/bin/python3",
  "/usr/bin/git",
  "/usr/bin/make",
  "/usr/bin/cc",
  "/usr/bin/c++",
] as const;

export type SandboxTermination =
  | "exit"
  | "timeout"
  | "aborted"
  | "output_limit"
  | "lock_conflict"
  | "signal";

export interface SandboxPolicy {
  workspace: string;
  gitDir: string;
  nodeRoot: string;
  bwrapPath: string;
  flockPath: string;
  etcMounts: string[];
  usrMergeLinks: Array<{ destination: string; target: string }>;
}

export interface PrepareSandboxOptions {
  platform?: NodeJS.Platform | string;
  bwrapPath?: string;
  flockPath?: string;
  nodeExecPath?: string;
  homeDir?: string;
  agentDir?: string;
  requireUserNamespaces?: boolean;
}

export interface TempStore {
  readonly root: string;
}

export interface RunSandboxOptions {
  command: string;
  timeoutSeconds?: number;
  signal?: AbortSignal;
  tempStore: TempStore;
  maxCaptureBytes?: number;
  onOutput?: (chunk: string) => void;
}

export interface TruncatedOutput {
  content: string;
  truncated: boolean;
  sanitized: boolean;
  totalBytes: number;
  shownBytes: number;
  totalLines: number;
  shownLines: number;
}

export interface SandboxRunResult {
  exitCode: number | null;
  signal: NodeJS.Signals | null;
  termination: SandboxTermination;
  output: TruncatedOutput;
  capturedOutputPath?: string;
  capturedBytes: number;
  observedBytes: number;
  durationMs: number;
}

function isWithin(parent: string, child: string): boolean {
  const rel = relative(parent, child);
  return rel === "" || (!rel.startsWith(`..${sep}`) && rel !== ".." && !isAbsolute(rel));
}

function hasControlCharacter(value: string): boolean {
  return /[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/.test(value);
}

async function assertExecutable(path: string, label: string): Promise<void> {
  await access(path, fsConstants.X_OK).catch(() => {
    throw new Error(`${label} is missing or not executable: ${path}`);
  });
}

async function assertFixedHostBinary(path: string, label: string): Promise<void> {
  const info = await lstat(path).catch(() => undefined);
  if (!info?.isFile()) throw new Error(`${label} must be a regular file: ${path}`);
  if (info.uid !== 0 || (info.mode & 0o022) !== 0) {
    throw new Error(`${label} must be root-owned and not group/world-writable: ${path}`);
  }
  if ((info.mode & 0o4000) !== 0) throw new Error(`${label} must not be setuid: ${path}`);
  await assertExecutable(path, label);
  const canonical = await realpath(path);
  if (canonical !== path) throw new Error(`${label} path must not resolve elsewhere: ${path} -> ${canonical}`);
}

async function pathExists(path: string): Promise<boolean> {
  try {
    await lstat(path);
    return true;
  } catch {
    return false;
  }
}

export function validateTimeoutSeconds(value: number | undefined): number {
  const timeout = value ?? DEFAULT_TIMEOUT_SECONDS;
  if (!Number.isInteger(timeout) || timeout < 1 || timeout > MAX_TIMEOUT_SECONDS) {
    throw new Error(`timeout must be an integer from 1 to ${MAX_TIMEOUT_SECONDS} seconds`);
  }
  return timeout;
}

export async function findNodeDistributionRoot(nodeExecPath: string): Promise<string> {
  const canonicalExec = await realpath(nodeExecPath).catch(() => {
    throw new Error(`Node executable is unavailable: ${nodeExecPath}`);
  });
  if (basename(canonicalExec) !== "node") {
    throw new Error(`Node executable must be named node: ${canonicalExec}`);
  }

  let cursor = dirname(canonicalExec);
  for (let depth = 0; depth < 5; depth++) {
    const candidate = basename(cursor) === "bin" ? dirname(cursor) : cursor;
    const candidateNode = join(candidate, "bin", "node");
    const candidateNpm = join(candidate, "bin", "npm");
    const candidateNpx = join(candidate, "bin", "npx");
    try {
      const nodeReal = await realpath(candidateNode);
      const npmReal = await realpath(candidateNpm);
      const npxReal = await realpath(candidateNpx);
      const rootReal = await realpath(candidate);
      if (
        nodeReal === canonicalExec &&
        isWithin(rootReal, npmReal) &&
        isWithin(rootReal, npxReal)
      ) {
        await Promise.all([
          assertExecutable(candidateNode, "node"),
          assertExecutable(candidateNpm, "npm"),
          assertExecutable(candidateNpx, "npx"),
        ]);
        return rootReal;
      }
    } catch {
      // Try the next ancestor.
    }
    const next = dirname(cursor);
    if (next === cursor) break;
    cursor = next;
  }
  throw new Error(`Could not locate a self-contained Node/npm/npx distribution above ${canonicalExec}`);
}

async function validateWorkspace(
  cwd: string,
  homeDir: string,
  agentDir: string,
): Promise<{ workspace: string; gitDir: string }> {
  if (hasControlCharacter(cwd)) throw new Error("Workspace path contains a control character");
  const workspace = await realpath(resolve(cwd)).catch(() => {
    throw new Error(`Workspace does not exist: ${cwd}`);
  });
  if (hasControlCharacter(workspace)) throw new Error("Canonical workspace path contains a control character");
  const workspaceInfo = await lstat(workspace);
  if (!workspaceInfo.isDirectory()) throw new Error(`Workspace is not a directory: ${workspace}`);

  const canonicalHome = await realpath(homeDir).catch(() => resolve(homeDir));
  const canonicalAgentDir = await realpath(agentDir).catch(() => resolve(agentDir));
  const sensitive = [
    "/",
    "/home",
    "/root",
    "/tmp",
    "/var",
    "/etc",
    "/usr",
    "/opt",
    "/proc",
    "/sys",
    "/dev",
    canonicalHome,
    canonicalAgentDir,
  ];
  for (const path of sensitive) {
    if (workspace === path || isWithin(workspace, path)) {
      throw new Error(`Workspace is too broad or contains a sensitive root: ${workspace}`);
    }
  }
  await access(workspace, fsConstants.R_OK | fsConstants.W_OK).catch(() => {
    throw new Error(`Workspace must be readable and writable: ${workspace}`);
  });

  const gitDir = join(workspace, ".git");
  const gitInfo = await lstat(gitDir).catch(() => undefined);
  if (!gitInfo?.isDirectory() || gitInfo.isSymbolicLink()) {
    throw new Error("Whitebox requires a normal root .git directory (worktrees and .git files are unsupported)");
  }
  const canonicalGit = await realpath(gitDir);
  if (canonicalGit !== gitDir || !isWithin(workspace, canonicalGit)) {
    throw new Error(`Root .git directory must resolve inside the workspace: ${gitDir}`);
  }
  await access(gitDir, fsConstants.R_OK).catch(() => {
    throw new Error(`Root .git directory is not readable: ${gitDir}`);
  });
  return { workspace, gitDir };
}

function decodeMountInfoPath(value: string): string {
  return value.replace(/\\(040|011|012|134)/g, (_match, octal: string) =>
    String.fromCharCode(Number.parseInt(octal, 8))
  );
}

export async function validateWorkspaceBoundary(workspace: string): Promise<void> {
  const mountInfo = await readFile("/proc/self/mountinfo", "utf8");
  for (const line of mountInfo.split("\n")) {
    if (!line) continue;
    const fields = line.split(" ");
    const mountPoint = fields[4] ? decodeMountInfoPath(fields[4]) : undefined;
    if (mountPoint && mountPoint !== workspace && isWithin(workspace, mountPoint)) {
      throw new Error(`Workspace contains a nested host mount: ${mountPoint}`);
    }
  }

  const gitDir = join(workspace, ".git");
  const hardlinks = new Map<string, {
    nlink: number;
    count: number;
    firstPath: string;
    inGit: boolean;
    outsideGit: boolean;
    inconsistent: boolean;
  }>();
  const recordFile = async (path: string) => {
    const info = await lstat(path);
    if (info.nlink <= 1) return;
    const key = `${info.dev}:${info.ino}`;
    const inGit = isWithin(gitDir, path);
    const current = hardlinks.get(key);
    if (current) {
      current.count++;
      current.inGit ||= inGit;
      current.outsideGit ||= !inGit;
      current.inconsistent ||= current.nlink !== info.nlink;
    } else {
      hardlinks.set(key, {
        nlink: info.nlink,
        count: 1,
        firstPath: path,
        inGit,
        outsideGit: !inGit,
        inconsistent: false,
      });
    }
  };

  const pending = [workspace];
  let visited = 0;
  while (pending.length > 0) {
    const directory = pending.pop()!;
    const handle = await opendir(directory);
    for await (const entry of handle) {
      visited++;
      if (visited > 1_000_000) throw new Error("Workspace safety scan exceeded 1,000,000 entries");
      const path = join(directory, entry.name);
      if (entry.isDirectory()) {
        pending.push(path);
      } else if (entry.isSymbolicLink()) {
        // Symlinks resolve inside the sandbox namespace.
      } else if (entry.isFile()) {
        await recordFile(path);
      } else {
        const info = await lstat(path);
        if (info.isDirectory()) pending.push(path);
        else if (info.isSymbolicLink()) continue;
        else if (info.isFile()) await recordFile(path);
        else throw new Error(`Workspace contains an unsupported IPC or device node: ${path}`);
      }
    }
  }

  for (const record of hardlinks.values()) {
    if (record.inconsistent || record.count !== record.nlink) {
      throw new Error(`Workspace contains a hard-linked regular file with a link outside the workspace: ${record.firstPath}`);
    }
    if (record.inGit && record.outsideGit) {
      throw new Error(`Workspace contains a hard link that bypasses the read-only .git mount: ${record.firstPath}`);
    }
  }
}

export async function prepareSandbox(
  cwd: string,
  options: PrepareSandboxOptions = {},
): Promise<SandboxPolicy> {
  const platform = options.platform ?? process.platform;
  if (platform !== "linux") throw new Error(`Whitebox supports Linux only, not ${platform}`);

  const bwrapPath = options.bwrapPath ?? BWRAP_PATH;
  const flockPath = options.flockPath ?? FLOCK_PATH;
  if (bwrapPath !== BWRAP_PATH || flockPath !== FLOCK_PATH) {
    throw new Error("Whitebox requires the fixed /usr/bin/bwrap and /usr/bin/flock paths");
  }
  await Promise.all([
    assertFixedHostBinary(bwrapPath, "bubblewrap"),
    assertFixedHostBinary(flockPath, "flock"),
  ]);

  if (options.requireUserNamespaces !== false && (await pathExists("/proc/sys/kernel/unprivileged_userns_clone"))) {
    const value = (await readFile("/proc/sys/kernel/unprivileged_userns_clone", "utf8")).trim();
    if (value !== "1") throw new Error("Unprivileged user namespaces are disabled");
  }

  await Promise.all(REQUIRED_USR_TOOLS.map((path) => assertExecutable(path, basename(path))));
  const nodeRoot = await findNodeDistributionRoot(options.nodeExecPath ?? process.execPath);
  const { workspace, gitDir } = await validateWorkspace(
    cwd,
    options.homeDir ?? homedir(),
    options.agentDir ?? join(homedir(), ".pi", "agent"),
  );
  if (isWithin(workspace, nodeRoot) || isWithin(nodeRoot, workspace)) {
    throw new Error("Workspace and the Pi Node distribution must not overlap");
  }
  await validateWorkspaceBoundary(workspace);

  const etcCandidates = [
    "/etc/passwd",
    "/etc/group",
    "/etc/nsswitch.conf",
    "/etc/ld.so.cache",
    "/etc/alternatives",
    "/etc/localtime",
  ];
  const etcMounts: string[] = [];
  for (const path of etcCandidates) {
    if (await pathExists(path)) etcMounts.push(path);
  }

  const usrMergeLinks: Array<{ destination: string; target: string }> = [];
  for (const [destination, target] of [
    ["/bin", "usr/bin"],
    ["/sbin", "usr/sbin"],
    ["/lib", "usr/lib"],
    ["/lib64", "usr/lib64"],
  ] as const) {
    if (await pathExists(`/${target}`)) usrMergeLinks.push({ destination, target });
  }

  return {
    workspace,
    gitDir,
    nodeRoot,
    bwrapPath,
    flockPath,
    etcMounts,
    usrMergeLinks,
  };
}

const INNER_ENV: ReadonlyArray<readonly [string, string]> = [
  ["PATH", "/opt/node/bin:/usr/bin:/bin"],
  ["PWD", "/workspace"],
  ["HOME", "/home/whitebox"],
  ["USER", "whitebox"],
  ["LOGNAME", "whitebox"],
  ["SHELL", "/bin/bash"],
  ["LANG", "C.UTF-8"],
  ["LC_ALL", "C.UTF-8"],
  ["TMPDIR", "/tmp"],
  ["XDG_CACHE_HOME", "/tmp/xdg-cache"],
  ["XDG_CONFIG_HOME", "/home/whitebox/.config"],
  ["XDG_DATA_HOME", "/home/whitebox/.local/share"],
  ["XDG_STATE_HOME", "/tmp/xdg-state"],
  ["CI", "1"],
  ["TERM", "dumb"],
  ["NO_COLOR", "1"],
  ["PAGER", "cat"],
  ["GIT_PAGER", "cat"],
  ["GIT_TERMINAL_PROMPT", "0"],
  ["GIT_CONFIG_NOSYSTEM", "1"],
  ["GIT_CONFIG_GLOBAL", "/dev/null"],
  ["GIT_ASKPASS", "/bin/false"],
  ["NPM_CONFIG_OFFLINE", "true"],
  ["NPM_CONFIG_CACHE", "/tmp/npm-cache"],
  ["NPM_CONFIG_USERCONFIG", "/dev/null"],
  ["NPM_CONFIG_UPDATE_NOTIFIER", "false"],
  ["NPM_CONFIG_AUDIT", "false"],
  ["NPM_CONFIG_FUND", "false"],
  ["PIP_NO_INDEX", "1"],
  ["PIP_DISABLE_PIP_VERSION_CHECK", "1"],
  ["PYTHONNOUSERSITE", "1"],
] as const;

export function buildBwrapBaseArgs(policy: SandboxPolicy): string[] {
  const args = [
    "--unshare-user",
    "--disable-userns",
    "--unshare-pid",
    "--unshare-ipc",
    "--unshare-uts",
    "--unshare-net",
    "--unshare-cgroup-try",
    "--hostname",
    "whitebox",
    "--new-session",
    "--die-with-parent",
    "--cap-drop",
    "ALL",
    "--clearenv",
  ];
  for (const [name, value] of INNER_ENV) args.push("--setenv", name, value);

  args.push("--ro-bind", "/usr", "/usr");
  args.push("--ro-bind", policy.nodeRoot, "/opt/node");
  for (const link of policy.usrMergeLinks) args.push("--symlink", link.target, link.destination);
  for (const path of policy.etcMounts) args.push("--ro-bind", path, path);

  args.push("--proc", "/proc", "--dev", "/dev");
  args.push("--perms", "1777", "--size", String(TMP_SIZE_BYTES), "--tmpfs", "/tmp");
  args.push("--perms", "0755", "--size", String(HOME_SIZE_BYTES), "--tmpfs", "/home");
  args.push("--perms", "0755", "--size", String(RUN_SIZE_BYTES), "--tmpfs", "/run");
  args.push("--perms", "0700", "--dir", "/home/whitebox");
  args.push("--perms", "0700", "--dir", "/home/whitebox/.config");
  args.push("--perms", "0700", "--dir", "/home/whitebox/.local");
  args.push("--perms", "0700", "--dir", "/home/whitebox/.local/share");
  args.push("--perms", "0700", "--dir", "/tmp/xdg-cache");
  args.push("--perms", "0700", "--dir", "/tmp/xdg-state");
  args.push("--perms", "0700", "--dir", "/tmp/npm-cache");
  args.push("--dir", "/workspace");
  args.push("--bind", policy.workspace, "/workspace");
  args.push("--ro-bind", policy.gitDir, "/workspace/.git");
  return args;
}

export function buildBwrapArgs(policy: SandboxPolicy, command: string): string[] {
  if (!command.trim()) throw new Error("command must not be empty");
  if (command.includes("\0")) throw new Error("command must not contain NUL bytes");

  const args = buildBwrapBaseArgs(policy);
  args.push("--remount-ro", "/");
  args.push("--chdir", "/workspace");
  args.push("--", "/bin/bash", "--noprofile", "--norc", "-c", command);
  return args;
}

export function buildFlockArgs(policy: SandboxPolicy, command: string): string[] {
  return [
    "--exclusive",
    "--nonblock",
    "--conflict-exit-code",
    String(LOCK_CONFLICT_EXIT_CODE),
    "--close",
    policy.workspace,
    policy.bwrapPath,
    ...buildBwrapArgs(policy, command),
  ];
}

export async function createTempStore(): Promise<TempStore> {
  const root = await mkdtemp(join(tmpdir(), TEMP_PREFIX));
  await chmod(root, 0o700);
  return Object.freeze({ root });
}

export async function cleanupTempStore(store: TempStore | undefined): Promise<void> {
  if (!store) return;
  const tempRoot = await realpath(tmpdir());
  const resolvedRoot = resolve(store.root);
  if (dirname(resolvedRoot) !== tempRoot || !basename(resolvedRoot).startsWith(TEMP_PREFIX)) {
    throw new Error(`Refusing to remove a non-Whitebox temp path: ${store.root}`);
  }
  await rm(resolvedRoot, { recursive: true, force: true });
}

export function sanitizeDisplayText(value: string): string {
  return value.replace(/[\u0000-\u0008\u000b-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g, "?");
}

export function truncateOutputBuffer(
  buffer: Buffer,
  maxBytes = DISPLAY_MAX_BYTES,
  maxLines = DISPLAY_MAX_LINES,
): TruncatedOutput {
  const totalBytes = buffer.length;
  let totalLines = totalBytes === 0 ? 0 : 1;
  for (const byte of buffer) {
    if (byte === 0x0a) totalLines++;
  }

  let byteStart = Math.max(0, totalBytes - maxBytes);
  while (byteStart < totalBytes && (buffer[byteStart]! & 0xc0) === 0x80) byteStart++;
  let content = buffer.subarray(byteStart).toString("utf8");
  let lineCut = 0;
  let newlinesFromEnd = 0;
  for (let index = content.length - 1; index >= 0; index--) {
    if (content.charCodeAt(index) !== 0x0a) continue;
    newlinesFromEnd++;
    if (newlinesFromEnd >= maxLines) {
      lineCut = index + 1;
      break;
    }
  }
  if (lineCut > 0) content = content.slice(lineCut);

  const sanitizedContent = sanitizeDisplayText(content);
  const sanitized = sanitizedContent !== content;
  content = sanitizedContent;
  const shownBytes = Buffer.byteLength(content);
  let shownLines = content.length === 0 ? 0 : 1;
  for (let index = 0; index < content.length; index++) {
    if (content.charCodeAt(index) === 0x0a) shownLines++;
  }
  return {
    content,
    truncated: byteStart > 0 || lineCut > 0 || shownLines < totalLines,
    sanitized,
    totalBytes,
    shownBytes,
    totalLines,
    shownLines,
  };
}

export function truncateOutput(
  output: string,
  maxBytes = DISPLAY_MAX_BYTES,
  maxLines = DISPLAY_MAX_LINES,
): TruncatedOutput {
  return truncateOutputBuffer(Buffer.from(output), maxBytes, maxLines);
}

function signalNumber(signal: NodeJS.Signals | null): number | undefined {
  if (!signal) return undefined;
  return ({ SIGTERM: 15, SIGKILL: 9, SIGINT: 2, SIGHUP: 1 } as Partial<Record<NodeJS.Signals, number>>)[signal];
}

function killProcessGroup(pid: number | undefined, signal: NodeJS.Signals): boolean {
  if (!pid) return false;
  try {
    process.kill(-pid, signal);
    return true;
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (code === "ESRCH") return false;
    throw error;
  }
}

export async function runSandbox(
  policy: SandboxPolicy,
  options: RunSandboxOptions,
): Promise<SandboxRunResult> {
  const timeoutSeconds = validateTimeoutSeconds(options.timeoutSeconds);
  const maxCaptureBytes = options.maxCaptureBytes ?? MAX_CAPTURE_BYTES;
  if (!Number.isInteger(maxCaptureBytes) || maxCaptureBytes < 1 || maxCaptureBytes > MAX_CAPTURE_BYTES) {
    throw new Error(`maxCaptureBytes must be an integer from 1 to ${MAX_CAPTURE_BYTES}`);
  }
  if (options.signal?.aborted) throw new Error("Whitebox run was cancelled before start");
  await validateWorkspaceBoundary(policy.workspace);

  const flockArgs = buildFlockArgs(policy, options.command);
  const startedAt = Date.now();
  const child = spawn(policy.flockPath, flockArgs, {
    cwd: "/",
    env: { PATH: "/usr/bin:/bin", LANG: "C", LC_ALL: "C" },
    detached: true,
    shell: false,
    stdio: ["ignore", "pipe", "pipe"],
  });

  const captured: Buffer[] = [];
  let capturedBytes = 0;
  let observedBytes = 0;
  let stopReason: "timeout" | "aborted" | "output_limit" | undefined;
  let killTimer: ReturnType<typeof setTimeout> | undefined;
  let timeoutTimer: ReturnType<typeof setTimeout> | undefined;

  const terminate = (signal: NodeJS.Signals) => {
    try {
      if (killProcessGroup(child.pid, signal)) return;
    } catch {
      // Fall through to killing the direct flock process. bwrap uses
      // --die-with-parent, so losing flock still closes the sandbox tree.
    }
    try {
      child.kill(signal);
    } catch {
      // The process has already exited. The close event remains authoritative.
    }
  };
  const requestStop = (reason: typeof stopReason) => {
    if (stopReason) return;
    stopReason = reason;
    terminate("SIGTERM");
    killTimer = setTimeout(() => terminate("SIGKILL"), 300);
    killTimer.unref?.();
  };

  const consume = (chunk: Buffer) => {
    observedBytes += chunk.length;
    const remaining = maxCaptureBytes - capturedBytes;
    if (remaining > 0) {
      const kept = chunk.subarray(0, remaining);
      captured.push(Buffer.from(kept));
      capturedBytes += kept.length;
      if (kept.length > 0) {
        try {
          options.onOutput?.(sanitizeDisplayText(kept.toString("utf8")));
        } catch {
          // Rendering progress is best-effort and must not destabilize process control.
        }
      }
    }
    if (observedBytes > maxCaptureBytes) requestStop("output_limit");
  };
  child.stdout.on("data", consume);
  child.stderr.on("data", consume);

  const onAbort = () => requestStop("aborted");
  options.signal?.addEventListener("abort", onAbort, { once: true });
  if (options.signal?.aborted) requestStop("aborted");
  timeoutTimer = setTimeout(() => requestStop("timeout"), timeoutSeconds * 1000);
  timeoutTimer.unref?.();

  const closed = await new Promise<{ code: number | null; signal: NodeJS.Signals | null }>((resolveClose, reject) => {
    child.once("error", reject);
    child.once("close", (code, signal) => resolveClose({ code, signal }));
  }).finally(() => {
    if (timeoutTimer) clearTimeout(timeoutTimer);
    if (killTimer) clearTimeout(killTimer);
    options.signal?.removeEventListener("abort", onAbort);
  });

  const rawBuffer = Buffer.concat(captured, capturedBytes);
  const output = truncateOutputBuffer(rawBuffer);
  let capturedOutputPath: string | undefined;
  if (output.truncated || output.sanitized || stopReason === "output_limit") {
    for (const entry of await readdir(options.tempStore.root, { withFileTypes: true })) {
      if (entry.isFile() && entry.name.startsWith("output-") && entry.name.endsWith(".log")) {
        await rm(join(options.tempStore.root, entry.name), { force: true });
      }
    }
    capturedOutputPath = join(options.tempStore.root, `output-${randomUUID()}.log`);
    await writeFile(capturedOutputPath, rawBuffer, { flag: "wx", mode: 0o600 });
  }

  let termination: SandboxTermination;
  if (stopReason) termination = stopReason;
  else if (closed.code === LOCK_CONFLICT_EXIT_CODE) termination = "lock_conflict";
  else if (closed.signal) termination = "signal";
  else termination = "exit";

  const signalExit = signalNumber(closed.signal);
  return {
    exitCode: closed.code ?? (signalExit === undefined ? null : 128 + signalExit),
    signal: closed.signal,
    termination,
    output,
    capturedOutputPath,
    capturedBytes,
    observedBytes,
    durationMs: Date.now() - startedAt,
  };
}

export function policySummary(policy: SandboxPolicy, timeoutSeconds: number): string {
  const safeWorkspace = sanitizeDisplayText(policy.workspace);
  const workspace = safeWorkspace.length > 1_024
    ? `…${safeWorkspace.slice(-1_023)}`
    : safeWorkspace;
  return [
    `workspace=${workspace} -> /workspace (read/write)`,
    ".git=/workspace/.git (read-only)",
    "network=isolated (no exceptions)",
    "home=/home/whitebox (temporary)",
    `timeout=${timeoutSeconds}s`,
  ].join("; ");
}

export async function assertTempStoreRemoved(store: TempStore): Promise<boolean> {
  try {
    await stat(store.root);
    return false;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === "ENOENT";
  }
}
