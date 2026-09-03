import { spawn } from "node:child_process";
import { constants as fsConstants } from "node:fs";
import { access, lstat, open, realpath, type FileHandle } from "node:fs/promises";
import { homedir } from "node:os";
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import {
  buildBwrapBaseArgs,
  LOCK_CONFLICT_EXIT_CODE,
  sanitizeDisplayText,
  validateWorkspaceBoundary,
  type SandboxPolicy,
  type TempStore,
} from "./sandbox.ts";

export const FILE_TOOL_NAMES = ["read", "write", "edit", "grep", "find", "ls"] as const;
export type FileToolName = (typeof FILE_TOOL_NAMES)[number];

const FILE_TOOL_SET = new Set<string>(FILE_TOOL_NAMES);
const WORKER_PATH = fileURLToPath(new URL("./file-worker.ts", import.meta.url));
const WORKER_SANDBOX_PATH = "/opt/whitebox-file-worker.ts";
const CAPTURE_SANDBOX_PATH = "/whitebox-capture/output.log";
const MAX_WORKER_OUTPUT_BYTES = 64 * 1024 * 1024;
export const FILE_TOOL_TIMEOUT_SECONDS = 120;
const FILE_TOOL_KILL_GRACE_MS = 300;
const UNICODE_SPACES = /[\u00a0\u2000-\u200a\u202f\u205f\u3000]/g;

export interface CaptureRecord {
  readonly sourcePath: string;
  readonly realPath: string;
  readonly dev: number;
  readonly ino: number;
  readonly size: number;
  readonly ctimeMs: number;
}

export interface BoundaryToolRequest {
  toolName: FileToolName;
  params: Record<string, unknown>;
  modelSupportsImages: boolean;
  captures?: readonly CaptureRecord[];
}

export function sanitizeCaptureResult(result: any): any {
  if (!result || !Array.isArray(result.content)) return result;
  return {
    ...result,
    content: result.content.map((block: any) =>
      block?.type === "text" && typeof block.text === "string"
        ? { ...block, text: sanitizeDisplayText(block.text) }
        : block
    ),
  };
}

type AuthorizedPath = {
  workerPath: string;
  capture?: CaptureRecord;
};

function isWithin(parent: string, child: string): boolean {
  const rel = relative(parent, child);
  return rel === "" || (!rel.startsWith(`..${sep}`) && rel !== ".." && !isAbsolute(rel));
}

function isMissingPathError(error: unknown): boolean {
  const code = (error as NodeJS.ErrnoException)?.code;
  return code === "ENOENT" || code === "ENOTDIR";
}

function normalizeInputPath(input: string, workspace: string): string {
  if (/[\u0000-\u001f\u007f-\u009f]/.test(input)) throw new Error("File path contains a control character");
  let normalized = input.replace(UNICODE_SPACES, " ");
  if (normalized.startsWith("@")) normalized = normalized.slice(1);
  if (normalized === "~") normalized = homedir();
  else if (normalized.startsWith("~/")) normalized = join(homedir(), normalized.slice(2));
  if (normalized.startsWith("file://")) {
    try {
      normalized = fileURLToPath(normalized);
    } catch {
      throw new Error("File path contains an invalid file URL");
    }
  }
  return isAbsolute(normalized) ? resolve(normalized) : resolve(workspace, normalized);
}

// A new file has no realpath yet. Canonicalize its nearest existing ancestor so
// a symlinked parent cannot redirect the eventual write outside the workspace.
async function canonicalizeForWrite(path: string): Promise<{ canonical: string; exists: boolean }> {
  try {
    return { canonical: await realpath(path), exists: true };
  } catch (error) {
    if (!isMissingPathError(error)) throw error;
  }

  let cursor = dirname(path);
  while (true) {
    try {
      const ancestor = await realpath(cursor);
      return { canonical: join(ancestor, relative(cursor, path)), exists: false };
    } catch (error) {
      if (!isMissingPathError(error)) throw error;
    }
    const parent = dirname(cursor);
    if (parent === cursor) throw new Error(`Could not canonicalize a parent of ${path}`);
    cursor = parent;
  }
}

// Captures are the only intentional read exception outside the workspace. Pin
// their identity and metadata so a path replacement is rejected fail-closed.
async function assertCaptureCurrent(record: CaptureRecord): Promise<void> {
  const info = await lstat(record.sourcePath).catch(() => undefined);
  if (
    !info?.isFile() ||
    info.isSymbolicLink() ||
    info.dev !== record.dev ||
    info.ino !== record.ino ||
    info.size !== record.size ||
    info.ctimeMs !== record.ctimeMs
  ) {
    throw new Error("Whitebox capture ownership changed");
  }
  const canonical = await realpath(record.sourcePath).catch(() => undefined);
  if (canonical !== record.realPath) throw new Error("Whitebox capture path changed");
  await access(record.sourcePath, fsConstants.R_OK);
}

export async function registerCapture(store: TempStore, capturePath: string): Promise<CaptureRecord> {
  const root = await realpath(store.root).catch(() => {
    throw new Error("Whitebox capture store is unavailable");
  });
  const rootInfo = await lstat(store.root);
  if (!rootInfo.isDirectory() || rootInfo.isSymbolicLink() || (rootInfo.mode & 0o077) !== 0) {
    throw new Error("Whitebox capture store ownership check failed");
  }
  if (resolve(store.root) !== root) throw new Error("Whitebox capture store path changed");
  if (typeof process.getuid === "function" && rootInfo.uid !== process.getuid()) {
    throw new Error("Whitebox capture store is owned by another user");
  }

  const resolved = resolve(capturePath);
  const canonical = await realpath(resolved).catch(() => {
    throw new Error("Whitebox capture file is unavailable");
  });
  if (dirname(canonical) !== root || !/^output-[0-9a-f-]+\.log$/i.test(basename(canonical))) {
    throw new Error("Captured output is not owned by this Whitebox store");
  }
  const info = await lstat(resolved);
  if (!info.isFile() || info.isSymbolicLink()) throw new Error("Whitebox capture must be a regular file");
  if (typeof process.getuid === "function" && info.uid !== process.getuid()) {
    throw new Error("Whitebox capture is owned by another user");
  }
  const record = Object.freeze({
    sourcePath: resolved,
    realPath: canonical,
    dev: info.dev,
    ino: info.ino,
    size: info.size,
    ctimeMs: info.ctimeMs,
  });
  await assertCaptureCurrent(record);
  return record;
}

async function authorizePath(
  policy: SandboxPolicy,
  rawPath: string,
  accessMode: "read" | "write",
  mustExist: boolean,
  captures: readonly CaptureRecord[] | undefined,
): Promise<AuthorizedPath> {
  const logical = normalizeInputPath(rawPath, policy.workspace);

  // Never grant the capture exception to write/edit, even for a registered path.
  const capture = accessMode === "read" ? captures?.find((record) => logical === record.sourcePath) : undefined;
  if (capture) {
    await assertCaptureCurrent(capture);
    return { workerPath: CAPTURE_SANDBOX_PATH, capture };
  }
  if (!isWithin(policy.workspace, logical)) {
    throw new Error(`Whitebox file tools cannot access paths outside the workspace: ${rawPath}`);
  }

  let canonical: string;
  // The host-side check provides clear errors and narrows mounts. Bubblewrap is
  // still the authoritative boundary if a path changes after this check.
  if (accessMode === "write") {
    const result = await canonicalizeForWrite(logical);
    if (mustExist && !result.exists) throw new Error(`Path not found: ${rawPath}`);
    canonical = result.canonical;
  } else {
    canonical = await realpath(logical).catch(() => {
      throw new Error(`Path not found or could not be canonicalized: ${rawPath}`);
    });
  }
  if (!isWithin(policy.workspace, canonical)) {
    throw new Error(`Whitebox file tools cannot follow a path outside the workspace: ${rawPath}`);
  }
  if (accessMode === "write" && (isWithin(policy.gitDir, logical) || isWithin(policy.gitDir, canonical))) {
    throw new Error(`Whitebox file tools cannot modify .git: ${rawPath}`);
  }

  const rel = relative(policy.workspace, logical);
  return { workerPath: rel || "." };
}

export function isFileToolName(name: string): name is FileToolName {
  return FILE_TOOL_SET.has(name);
}

export async function prepareBoundaryToolRequest(
  policy: SandboxPolicy,
  request: BoundaryToolRequest,
): Promise<{ params: Record<string, unknown>; capture?: CaptureRecord }> {
  const params = { ...request.params };
  const defaultPath = request.toolName === "grep" || request.toolName === "find" || request.toolName === "ls";
  const rawPath = typeof params.path === "string" ? params.path : defaultPath ? "." : undefined;
  if (rawPath === undefined) throw new Error(`${request.toolName} requires a path`);

  const accessMode = request.toolName === "write" || request.toolName === "edit" ? "write" : "read";
  const authorized = await authorizePath(
    policy,
    rawPath,
    accessMode,
    request.toolName !== "write",
    request.captures,
  );
  if (typeof params.path === "string" || !defaultPath) params.path = authorized.workerPath;
  return { params, capture: authorized.capture };
}

function terminateProcessGroup(pid: number | undefined, signal: NodeJS.Signals): void {
  if (!pid) return;
  try {
    process.kill(-pid, signal);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ESRCH") throw error;
  }
}

async function runBoundaryFileToolInternal(
  policy: SandboxPolicy,
  request: BoundaryToolRequest,
  signal: AbortSignal,
): Promise<any> {
  if (signal?.aborted) throw new Error("Operation aborted");
  // Re-scan immediately before every operation: a project may have changed
  // since startup or since the previous Whitebox command.
  await validateWorkspaceBoundary(policy.workspace, signal);
  signal.throwIfAborted();
  const prepared = await prepareBoundaryToolRequest(policy, request);
  signal.throwIfAborted();
  if (prepared.capture) await assertCaptureCurrent(prepared.capture);
  signal.throwIfAborted();

  await access(WORKER_PATH, fsConstants.R_OK).catch(() => {
    throw new Error("Whitebox file worker is unavailable");
  });
  const canonicalWorkerPath = await realpath(WORKER_PATH);
  signal.throwIfAborted();
  let captureHandle: FileHandle | undefined;
  if (prepared.capture) {
    // Open with O_NOFOLLOW and bind the descriptor, not the pathname. This
    // closes the capture-file check/use race before Bubblewrap starts.
    captureHandle = await open(prepared.capture.sourcePath, fsConstants.O_RDONLY | fsConstants.O_NOFOLLOW);
    const info = await captureHandle.stat().catch(async (error) => {
      await captureHandle?.close();
      throw error;
    });
    if (
      !info.isFile() ||
      info.dev !== prepared.capture.dev ||
      info.ino !== prepared.capture.ino ||
      info.size !== prepared.capture.size ||
      info.ctimeMs !== prepared.capture.ctimeMs
    ) {
      await captureHandle.close();
      throw new Error("Whitebox capture ownership changed before mounting");
    }
  }

  if (signal.aborted) {
    await captureHandle?.close();
    signal.throwIfAborted();
  }

  // The worker sees only /workspace, read-only .git, the fixed Pi runtime, and
  // (when needed) one descriptor-pinned read-only capture file.
  const bwrapArgs = buildBwrapBaseArgs(policy);
  bwrapArgs.push("--ro-bind", canonicalWorkerPath, WORKER_SANDBOX_PATH);
  if (captureHandle) {
    bwrapArgs.push("--dir", "/whitebox-capture");
    bwrapArgs.push("--ro-bind", "/proc/self/fd/3", CAPTURE_SANDBOX_PATH);
  }
  bwrapArgs.push("--remount-ro", "/", "--chdir", "/workspace");
  bwrapArgs.push(
    "--",
    "/opt/node/bin/node",
    "--no-warnings",
    "--experimental-strip-types",
    WORKER_SANDBOX_PATH,
  );

  const flockArgs = [
    "--exclusive",
    "--nonblock",
    "--conflict-exit-code",
    String(LOCK_CONFLICT_EXIT_CODE),
    "--close",
    policy.workspace,
    policy.bwrapPath,
    ...bwrapArgs,
  ];
  let child: ReturnType<typeof spawn>;
  try {
    child = spawn(policy.flockPath, flockArgs, {
      cwd: "/",
      env: { PATH: "/usr/bin:/bin", LANG: "C", LC_ALL: "C" },
      detached: true,
      shell: false,
      stdio: captureHandle
        ? ["pipe", "pipe", "pipe", captureHandle.fd]
        : ["pipe", "pipe", "pipe"],
    });
  } catch (error) {
    await captureHandle?.close();
    throw error;
  }

  if (!child.stdin || !child.stdout || !child.stderr) {
    terminateProcessGroup(child.pid, "SIGKILL");
    await captureHandle?.close();
    throw new Error("Whitebox file worker pipes are unavailable");
  }

  const stdout: Buffer[] = [];
  const stderr: Buffer[] = [];
  let stdoutBytes = 0;
  let stderrBytes = 0;
  let outputExceeded = false;
  const consume = (target: Buffer[], chunk: Buffer, isStdout: boolean) => {
    if (isStdout) {
      stdoutBytes += chunk.length;
      if (stdoutBytes > MAX_WORKER_OUTPUT_BYTES) {
        outputExceeded = true;
        terminateProcessGroup(child.pid, "SIGKILL");
        return;
      }
    } else {
      stderrBytes += chunk.length;
      if (stderrBytes > 64 * 1024) return;
    }
    target.push(Buffer.from(chunk));
  };
  child.stdout.on("data", (chunk: Buffer) => consume(stdout, chunk, true));
  child.stderr.on("data", (chunk: Buffer) => consume(stderr, chunk, false));

  let killTimer: ReturnType<typeof setTimeout> | undefined;
  const onAbort = () => {
    terminateProcessGroup(child.pid, "SIGTERM");
    killTimer = setTimeout(() => terminateProcessGroup(child.pid, "SIGKILL"), FILE_TOOL_KILL_GRACE_MS);
    killTimer.unref?.();
  };
  signal.addEventListener("abort", onAbort, { once: true });
  if (signal.aborted) onAbort();
  child.stdin.on("error", () => undefined);
  child.stdin.end(JSON.stringify({
    toolName: request.toolName,
    params: prepared.params,
    modelSupportsImages: request.modelSupportsImages,
  }));

  const closed = await new Promise<{ code: number | null; signal: NodeJS.Signals | null }>((resolveClose, reject) => {
    child.once("error", reject);
    child.once("close", (code, childSignal) => resolveClose({ code, signal: childSignal }));
  }).finally(async () => {
    if (killTimer) clearTimeout(killTimer);
    signal.removeEventListener("abort", onAbort);
    await captureHandle?.close();
  });

  if (signal.aborted) throw new Error("Operation aborted");
  if (outputExceeded) throw new Error("Whitebox file tool output exceeded 64MiB");
  if (closed.code === LOCK_CONFLICT_EXIT_CODE) throw new Error("Another Whitebox operation is active for this workspace");

  const rawStdout = Buffer.concat(stdout).toString("utf8");
  let response: any;
  try {
    response = JSON.parse(rawStdout);
  } catch {
    const reason = sanitizeDisplayText(Buffer.concat(stderr).toString("utf8").trim());
    throw new Error(`Whitebox file worker returned an invalid response${reason ? `: ${reason}` : ""}`);
  }
  if (closed.code !== 0 || !response?.ok) {
    throw new Error(sanitizeDisplayText(response?.error ?? `Whitebox file worker exited with code ${closed.code}`));
  }
  // Capture files retain the exact raw bytes for evidence. Only text crossing
  // back into Pi/model context receives Whitebox's stronger display safety
  // treatment; ordinary workspace-file results preserve Pi's native behavior.
  return prepared.capture ? sanitizeCaptureResult(response.result) : response.result;
}

export async function runBoundaryFileTool(
  policy: SandboxPolicy,
  request: BoundaryToolRequest,
  signal?: AbortSignal,
  timeoutSeconds = FILE_TOOL_TIMEOUT_SECONDS,
): Promise<any> {
  if (!Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0 || timeoutSeconds > FILE_TOOL_TIMEOUT_SECONDS) {
    throw new Error(`Whitebox file tool timeout must be at most ${FILE_TOOL_TIMEOUT_SECONDS} seconds`);
  }
  if (signal?.aborted) throw new Error("Operation aborted");
  const timeoutController = new AbortController();
  let timedOut = false;
  const timeoutTimer = setTimeout(() => {
    timedOut = true;
    timeoutController.abort();
  }, timeoutSeconds * 1_000);
  timeoutTimer.unref?.();
  const combinedSignal = signal
    ? AbortSignal.any([signal, timeoutController.signal])
    : timeoutController.signal;
  try {
    return await runBoundaryFileToolInternal(policy, request, combinedSignal);
  } catch (error) {
    if (timedOut) {
      throw new Error(`Whitebox file tool timed out after ${timeoutSeconds} seconds`);
    }
    if (signal?.aborted) throw new Error("Operation aborted");
    throw error;
  } finally {
    clearTimeout(timeoutTimer);
  }
}
