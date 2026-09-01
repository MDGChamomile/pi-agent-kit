import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { createServer } from "node:net";
import {
  access,
  chmod,
  link,
  mkdir,
  mkdtemp,
  readFile,
  readlink,
  realpath,
  rm,
  stat,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  assessPiVersion,
  assertTrustedPathOutsideWorkspace,
  PI_PACKAGE_ROOT_ENV,
  resolvePiEntrypoint,
  resolvePiRuntime,
} from "./bin/resolve-pi.mjs";
import { createWhiteboxExtension, type WhiteboxDependencies } from "./index.ts";
import {
  FILE_TOOL_NAMES,
  registerCapture,
  runBoundaryFileTool,
  sanitizeCaptureResult,
} from "./file-boundary.ts";
import {
  assertTempStoreRemoved,
  buildBwrapArgs,
  buildFlockArgs,
  cleanupTempStore,
  createTempStore,
  DEFAULT_TIMEOUT_SECONDS,
  DISPLAY_MAX_BYTES,
  DISPLAY_MAX_LINES,
  findNodeDistributionRoot,
  HOME_SIZE_BYTES,
  LOCK_CONFLICT_EXIT_CODE,
  MAX_TIMEOUT_SECONDS,
  policySummary,
  prepareSandbox,
  RUN_SIZE_BYTES,
  runSandbox,
  sanitizeDisplayText,
  truncateOutput,
  TMP_SIZE_BYTES,
  truncateOutputBuffer,
  validateTimeoutSeconds,
  type SandboxPolicy,
  type SandboxRunResult,
  type TempStore,
} from "./sandbox.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const INDEX_PATH = join(HERE, "index.ts");
const TEST_PI_PACKAGE_ROOT = dirname(dirname(fileURLToPath(
  import.meta.resolve("@earendil-works/pi-coding-agent"),
)));

function prepareTestSandbox(
  cwd: string,
  options: Parameters<typeof prepareSandbox>[1] = {},
): ReturnType<typeof prepareSandbox> {
  return prepareSandbox(cwd, { piPackageRoot: TEST_PI_PACKAGE_ROOT, ...options });
}

async function makeFixture(label: string): Promise<{
  root: string;
  workspace: string;
  sibling: string;
  fakeHome: string;
}> {
  const root = await mkdtemp(join(tmpdir(), `whitebox-test-${label}-`));
  const workspace = join(root, "workspace");
  const sibling = join(root, "sibling");
  const fakeHome = join(root, "fake-home");
  await mkdir(join(workspace, ".git", "objects"), { recursive: true });
  await mkdir(join(workspace, ".git", "refs", "heads"), { recursive: true });
  await mkdir(sibling);
  await mkdir(fakeHome);
  await writeFile(join(workspace, ".git", "HEAD"), "ref: refs/heads/main\n");
  await writeFile(join(workspace, ".git", "config"), "[core]\n\trepositoryformatversion = 0\n\tbare = false\n");
  await writeFile(join(workspace, "source.txt"), "original\n");
  await writeFile(join(sibling, "secret.txt"), "host-secret\n");
  await writeFile(join(fakeHome, "credential.txt"), "credential-secret\n");
  await symlink(join(sibling, "secret.txt"), join(workspace, "escape-link"));
  return { root, workspace, sibling, fakeHome };
}

async function eventually(predicate: () => Promise<boolean>, timeoutMs = 3_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error("condition was not met before timeout");
}

async function processWithMarkerExists(marker: string): Promise<boolean> {
  const proc = await import("node:fs/promises");
  for (const entry of await proc.readdir("/proc", { withFileTypes: true })) {
    if (!entry.isDirectory() || !/^\d+$/.test(entry.name)) continue;
    try {
      const command = await readFile(`/proc/${entry.name}/cmdline`, "utf8");
      if (command.includes(marker)) return true;
    } catch {
      // Process exited or is unreadable.
    }
  }
  return false;
}

function successfulRun(output = ""): SandboxRunResult {
  return {
    exitCode: 0,
    signal: null,
    termination: "exit",
    output: {
      content: output,
      truncated: false,
      sanitized: false,
      totalBytes: Buffer.byteLength(output),
      shownBytes: Buffer.byteLength(output),
      totalLines: output ? output.split("\n").length : 0,
      shownLines: output ? output.split("\n").length : 0,
    },
    capturedBytes: Buffer.byteLength(output),
    observedBytes: Buffer.byteLength(output),
    durationMs: 1,
  };
}

const FAKE_POLICY: SandboxPolicy = {
  workspace: "/tmp/fake-workspace",
  gitDir: "/tmp/fake-workspace/.git",
  nodeRoot: "/opt/fake-node",
  piPackageRoot: "/opt/fake-pi-package",
  bwrapPath: "/usr/bin/bwrap",
  flockPath: "/usr/bin/flock",
  etcMounts: ["/etc/passwd"],
  usrMergeLinks: [{ destination: "/bin", target: "usr/bin" }],
};

function fakeContext(projectTrusted = false) {
  const statuses: Array<[string, string | undefined]> = [];
  const notifications: Array<[string, string]> = [];
  return {
    ctx: {
      cwd: "/tmp/fake-workspace",
      mode: "tui",
      hasUI: true,
      isProjectTrusted: () => projectTrusted,
      ui: {
        setStatus: (key: string, value: string | undefined) => statuses.push([key, value]),
        notify: (message: string, type: string) => notifications.push([message, type]),
      },
    },
    statuses,
    notifications,
  };
}

function makeFakePi(options: {
  flag?: boolean;
  active?: string[];
  existingTools?: Array<{ name: string; sourceInfo: { path: string; source: string } }>;
} = {}) {
  const handlers = new Map<string, Array<(event: any, ctx: any) => any>>();
  const active = [...(options.active ?? ["read", "write", "edit", "bash"])];
  let activeTools = active;
  const tools = ["read", "write", "edit", "grep", "find", "ls", "bash"].map((name) => ({
    name,
    description: `built-in ${name}`,
    parameters: { type: "object", properties: {} },
    promptGuidelines: [],
    sourceInfo: { path: `<builtin:${name}>`, source: "builtin" },
  }));
  for (const existing of options.existingTools ?? []) {
    const index = tools.findIndex((tool) => tool.name === existing.name);
    if (index >= 0) tools[index] = existing as any;
    else tools.push(existing as any);
  }
  const toolDefinitions = new Map<string, any>();
  let toolDefinition: any;
  const registeredFlags: string[] = [];

  const pi = {
    registerFlag(name: string) {
      registeredFlags.push(name);
    },
    getFlag(name: string) {
      return name === "whitebox" ? (options.flag ?? false) : undefined;
    },
    on(name: string, handler: (event: any, ctx: any) => any) {
      const list = handlers.get(name) ?? [];
      list.push(handler);
      handlers.set(name, list);
    },
    getActiveTools() {
      return [...activeTools];
    },
    setActiveTools(names: string[]) {
      activeTools = [...names];
    },
    getAllTools() {
      return [...tools];
    },
    registerTool(definition: any) {
      toolDefinition = definition;
      toolDefinitions.set(definition.name, definition);
      const metadata = {
        name: definition.name,
        description: definition.description,
        parameters: definition.parameters,
        promptGuidelines: definition.promptGuidelines,
        sourceInfo: { path: INDEX_PATH, source: "local" },
      };
      const index = tools.findIndex((tool) => tool.name === definition.name);
      if (index >= 0) tools[index] = metadata;
      else tools.push(metadata);
    },
  };

  const fire = async (name: string, event: any, ctx: any) => {
    let result: any;
    for (const handler of handlers.get(name) ?? []) {
      const next = await handler(event, ctx);
      if (next !== undefined) result = next;
    }
    return result;
  };
  return {
    pi,
    fire,
    get activeTools() {
      return [...activeTools];
    },
    get toolDefinition() {
      return toolDefinition;
    },
    toolDefinitions,
    registeredFlags,
    tools,
  };
}

function fakeDependencies(
  argv: string[],
  changes: Partial<WhiteboxDependencies> = {},
): { deps: Partial<WhiteboxDependencies>; cleaned: TempStore[] } {
  const cleaned: TempStore[] = [];
  const store = Object.freeze({ root: "/tmp/pi-whitebox-fake" });
  const deps: Partial<WhiteboxDependencies> = {
    argv,
    prepareSandbox: async () => FAKE_POLICY,
    runSandbox: async () => successfulRun(),
    createTempStore: async () => store,
    cleanupTempStore: async (value) => {
      if (value) cleaned.push(value);
    },
    ...changes,
  };
  return { deps, cleaned };
}

describe("pure policy and argument construction", () => {
  test("timeout bounds are deterministic", () => {
    assert.equal(validateTimeoutSeconds(undefined), DEFAULT_TIMEOUT_SECONDS);
    assert.equal(validateTimeoutSeconds(1), 1);
    assert.equal(validateTimeoutSeconds(MAX_TIMEOUT_SECONDS), MAX_TIMEOUT_SECONDS);
    assert.throws(() => validateTimeoutSeconds(0));
    assert.throws(() => validateTimeoutSeconds(MAX_TIMEOUT_SECONDS + 1));
    assert.throws(() => validateTimeoutSeconds(1.5));
  });

  test("current Node distribution contains node, npm, and npx", async () => {
    const root = await findNodeDistributionRoot(process.execPath);
    for (const name of ["node", "npm", "npx"]) {
      const executable = await realpath(join(root, "bin", name));
      assert.ok(executable.startsWith(`${root}/`), `${name} must resolve inside the Node distribution`);
      await access(executable);
    }
  });

  test("piw resolves Pi outside the workspace and prefers the current Node distribution", async () => {
    const root = await mkdtemp(join(tmpdir(), "whitebox-test-piw-path-"));
    const workspace = join(root, "workspace");
    const runtimeBin = join(root, "runtime", "bin");
    const projectBin = join(workspace, "node_modules", ".bin");
    const externalBin = join(root, "external-bin");
    try {
      await Promise.all([
        mkdir(workspace, { recursive: true }),
        mkdir(runtimeBin, { recursive: true }),
        mkdir(projectBin, { recursive: true }),
        mkdir(externalBin, { recursive: true }),
      ]);
      const trustedPi = join(runtimeBin, "pi");
      const projectPi = join(projectBin, "pi");
      const externalPi = join(externalBin, "pi");
      const makePiCandidate = async (
        candidate: string,
        packageRoot: string,
        bin = "dist/cli.js",
        version = "0.84.2",
      ) => {
        const entrypoint = join(packageRoot, bin);
        await mkdir(dirname(entrypoint), { recursive: true });
        await writeFile(join(packageRoot, "package.json"), JSON.stringify({
          name: "@earendil-works/pi-coding-agent",
          version,
          bin: { pi: bin },
        }));
        await writeFile(entrypoint, "#!/usr/bin/env node\n");
        await chmod(entrypoint, 0o755);
        await symlink(entrypoint, candidate);
        return { entrypoint, packageRoot };
      };
      const trusted = await makePiCandidate(
        trustedPi,
        join(root, "runtime", "lib", "node_modules", "@earendil-works", "pi-coding-agent"),
        "dist/bundle/cli.js",
        "0.84.3",
      );
      await makePiCandidate(
        projectPi,
        join(workspace, "fake-package", "@earendil-works", "pi-coding-agent"),
      );
      const external = await makePiCandidate(
        externalPi,
        join(root, "external-package", "@earendil-works", "pi-coding-agent"),
      );

      const trustedRuntime = resolvePiRuntime({
        cwd: workspace,
        execPath: join(runtimeBin, "node"),
        pathValue: projectBin,
      });
      assert.equal(trustedRuntime.entrypoint, await realpath(trusted.entrypoint));
      assert.equal(trustedRuntime.packageRoot, await realpath(trusted.packageRoot));
      assert.equal(trustedRuntime.version, "0.84.3");
      assert.equal(resolvePiEntrypoint({
        cwd: workspace,
        execPath: join(runtimeBin, "node"),
        pathValue: projectBin,
      }), trustedRuntime.entrypoint);

      await rm(trustedPi);
      assert.throws(() => resolvePiEntrypoint({
        cwd: workspace,
        execPath: join(runtimeBin, "node"),
        pathValue: projectBin,
      }), /outside the current workspace/);
      assert.equal(resolvePiEntrypoint({
        cwd: workspace,
        execPath: join(runtimeBin, "node"),
        pathValue: `${projectBin}:${externalBin}`,
      }), await realpath(external.entrypoint));

      const nestedManifest = join(dirname(external.entrypoint), "package.json");
      await writeFile(nestedManifest, JSON.stringify({ name: "not-pi" }));
      assert.throws(() => resolvePiEntrypoint({
        cwd: workspace,
        execPath: join(runtimeBin, "node"),
        pathValue: `${projectBin}:${externalBin}`,
      }), /outside the current workspace/);
      await rm(nestedManifest);

      await rm(externalPi);
      const unvalidatedPi = join(externalBin, "pi");
      const unvalidated = await makePiCandidate(
        unvalidatedPi,
        join(root, "unvalidated-package", "@earendil-works", "pi-coding-agent"),
        "dist/bundle/cli.js",
        "0.84.4",
      );
      const unvalidatedRuntime = resolvePiRuntime({
        cwd: workspace,
        execPath: join(runtimeBin, "node"),
        pathValue: externalBin,
      });
      assert.equal(unvalidatedRuntime.version, "0.84.4");
      assert.equal(unvalidatedRuntime.validated, false);

      await writeFile(join(unvalidated.packageRoot, "package.json"), JSON.stringify({
        name: "@earendil-works/pi-coding-agent",
        version: "0.84.1",
        bin: { pi: "dist/bundle/cli.js" },
      }));
      assert.throws(() => resolvePiEntrypoint({
        cwd: workspace,
        execPath: join(runtimeBin, "node"),
        pathValue: externalBin,
      }), /below the minimum 0\.84\.2/);
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });

  test("Pi version policy permits unvalidated patch releases only within the supported minor line", () => {
    assert.deepEqual(assessPiVersion("0.84.1"), {
      allowed: false,
      validated: false,
      reason: "version is below the minimum 0.84.2",
    });
    assert.deepEqual(assessPiVersion("0.84.2"), { allowed: true, validated: true });
    assert.deepEqual(assessPiVersion("0.84.4"), { allowed: true, validated: false });
    assert.deepEqual(assessPiVersion("0.84.4-rc.1"), {
      allowed: false,
      validated: false,
      reason: "prerelease versions are not supported",
    });
    assert.deepEqual(assessPiVersion("0.85.0"), {
      allowed: false,
      validated: false,
      reason: "version is outside the supported range >=0.84.2 <0.85.0",
    });
    assert.equal(assessPiVersion("1.0.0").allowed, false);
    assert.equal(assessPiVersion("not-semver").allowed, false);
  });

  test("workspace and trusted runtime paths cannot overlap", async () => {
    const fixture = await makeFixture("trusted-overlap");
    try {
      const nestedExtension = join(fixture.workspace, "trusted-extension");
      await mkdir(nestedExtension);
      assert.throws(
        () => assertTrustedPathOutsideWorkspace(fixture.workspace, nestedExtension, "test extension"),
        /must not overlap/,
      );
      await assert.rejects(
        () => prepareTestSandbox(fixture.workspace, { extensionRoot: nestedExtension }),
        /extension source must not overlap/,
      );
      await assert.rejects(
        () => prepareTestSandbox(fixture.workspace, { extensionRoot: fixture.root }),
        /extension source must not overlap/,
      );
    } finally {
      await rm(fixture.root, { recursive: true, force: true });
    }
  });

  test("workspace and .git validation reject broad roots and symlink .git", async () => {
    await assert.rejects(() => prepareTestSandbox("/"), /too broad|sensitive root/);
    const fixture = await makeFixture("symlink-git");
    try {
      await rm(join(fixture.workspace, ".git"), { recursive: true });
      await symlink(fixture.sibling, join(fixture.workspace, ".git"));
      await assert.rejects(() => prepareTestSandbox(fixture.workspace), /normal root \.git/);
    } finally {
      await rm(fixture.root, { recursive: true, force: true });
    }
  });

  test("workspace IPC nodes are rejected before they can bridge the mount namespace", async () => {
    const fixture = await makeFixture("socket");
    const socketPath = join(fixture.workspace, "host.sock");
    const server = createServer();
    try {
      await new Promise<void>((resolveListen, reject) => {
        server.once("error", reject);
        server.listen(socketPath, resolveListen);
      });
      await assert.rejects(() => prepareTestSandbox(fixture.workspace), /unsupported IPC or device node/);
    } finally {
      await new Promise<void>((resolveClose) => server.close(() => resolveClose()));
      await rm(fixture.root, { recursive: true, force: true });
    }
  });

  test("hard-linked host files are rejected instead of becoming workspace aliases", async () => {
    const fixture = await makeFixture("hardlink");
    try {
      const outsideAlias = join(fixture.workspace, "hardlink-secret");
      await link(join(fixture.sibling, "secret.txt"), outsideAlias);
      await assert.rejects(() => prepareTestSandbox(fixture.workspace), /hard-linked regular file/);
      await rm(outsideAlias);

      await link(join(fixture.workspace, "source.txt"), join(fixture.workspace, "source-copy.txt"));
      await prepareTestSandbox(fixture.workspace);

      await link(join(fixture.workspace, ".git", "config"), join(fixture.workspace, "git-config-alias"));
      await assert.rejects(() => prepareTestSandbox(fixture.workspace), /bypasses the read-only \.git mount/);
    } finally {
      await rm(fixture.root, { recursive: true, force: true });
    }
  });

  test("command remains one inner Bash argument and mount order is fail-closed", async () => {
    const fixture = await makeFixture("argv");
    try {
      const policy = await prepareTestSandbox(fixture.workspace, { homeDir: fixture.fakeHome });
      const command = `printf '%s\\n' \"a; touch /host-escape\"; printf done`;
      const args = buildBwrapArgs(policy, command);
      assert.deepEqual(args.slice(-6), ["--", "/bin/bash", "--noprofile", "--norc", "-c", command]);
      assert.ok(args.indexOf("--clearenv") >= 0);
      assert.deepEqual(args.filter((value) => value.startsWith("PI_")), ["PI_OFFLINE"]);
      assert.equal(args[args.indexOf("PI_OFFLINE") + 1], "1");
      assert.equal(args.some((value) => value.startsWith("SSH_")), false);
      assert.equal(
        args.some((value, index) => value === "--ro-bind" && args[index + 1] === policy.nodeRoot),
        false,
        "the complete host Node prefix must not be exposed",
      );
      assert.ok(args.includes(join(policy.nodeRoot, "bin", "node")));
      assert.ok(args.includes(join(policy.nodeRoot, "lib", "node_modules", "npm")));
      assert.ok(args.includes(policy.piPackageRoot));

      const workspaceBind = args.findIndex(
        (value, index) => value === "--bind" && args[index + 1] === policy.workspace,
      );
      const gitBind = args.findIndex(
        (value, index) => value === "--ro-bind" && args[index + 1] === policy.gitDir,
      );
      const rootReadonly = args.findIndex(
        (value, index) => value === "--remount-ro" && args[index + 1] === "/",
      );
      assert.ok(workspaceBind > 0 && gitBind > workspaceBind && rootReadonly > gitBind);

      const acquisitionMarker = "/tmp/whitebox-lock-acquired";
      const flockArgs = buildFlockArgs(policy, command, acquisitionMarker);
      assert.ok(flockArgs.includes("--close"));
      assert.equal(flockArgs[flockArgs.indexOf("--conflict-exit-code") + 1], String(LOCK_CONFLICT_EXIT_CODE));
      assert.equal(flockArgs[flockArgs.indexOf(policy.workspace) + 1], "/usr/bin/python3");
      assert.equal(flockArgs[flockArgs.indexOf(acquisitionMarker) + 1], "/usr/bin/bwrap");
    } finally {
      await rm(fixture.root, { recursive: true, force: true });
    }
  });

  test("capture result sanitization preserves source objects and removes display controls", () => {
    const rawText = "ansi\u001b[31m osc\u001b]0;title\u0007 nul\u0000 c1\u0085 bidi\u202e isolate\u2066";
    const original = { content: [{ type: "text", text: rawText }], details: { source: "capture" } };
    const sanitized = sanitizeCaptureResult(original);
    assert.equal(original.content[0]!.text, rawText);
    assert.notEqual(sanitized, original);
    assert.deepEqual(sanitized.details, original.details);
    assert.doesNotMatch(
      sanitized.content[0].text,
      /[\u0000-\u0008\u000b-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/,
    );
  });

  test("tail truncation observes both byte and line limits", () => {
    assert.equal(DISPLAY_MAX_BYTES, 12 * 1024);
    assert.equal(DISPLAY_MAX_LINES, 400);
    const defaultLimited = truncateOutput("x".repeat(DISPLAY_MAX_BYTES + 1));
    assert.equal(defaultLimited.truncated, true);
    assert.equal(defaultLimited.shownBytes, DISPLAY_MAX_BYTES);

    const lines = Array.from({ length: 10 }, (_, index) => `line-${index}`).join("\n");
    const truncated = truncateOutput(lines, 100, 3);
    assert.equal(truncated.truncated, true);
    assert.equal(truncated.shownLines, 3);
    assert.equal(truncated.content, "line-7\nline-8\nline-9");
    const bytes = truncateOutput("x".repeat(100), 10, 10);
    assert.equal(bytes.shownBytes, 10);
    assert.equal(bytes.truncated, true);
    const control = truncateOutput("safe\u001b[31mred");
    assert.equal(control.sanitized, true);
    assert.equal(control.content, "safe?[31mred");
    assert.equal(sanitizeDisplayText("tab\tok\r\u202espoof"), "tab\tok??spoof");
    assert.equal(control.truncated, false);
    const newlineFlood = truncateOutputBuffer(Buffer.alloc(1_000_000, 0x0a), 1_024, 100);
    assert.ok(newlineFlood.shownBytes <= 1_024);
    assert.ok(newlineFlood.shownLines <= 100);
    assert.equal(newlineFlood.truncated, true);
  });
});

describe("Pi extension wiring with a fake API", () => {
  test("inactive mode registers only inert hooks and leaves tools unchanged", async () => {
    const made = makeFakePi();
    const { deps } = fakeDependencies([]);
    createWhiteboxExtension(deps)(made.pi as any);
    const { ctx, statuses } = fakeContext();
    await made.fire("session_start", { reason: "startup" }, ctx);
    assert.deepEqual(made.activeTools, ["read", "write", "edit", "bash"]);
    assert.equal(made.toolDefinition, undefined);
    assert.deepEqual(statuses, []);
    assert.deepEqual(await made.fire("tool_call", { toolName: "bash", input: { command: "true" } }, ctx), undefined);
    assert.deepEqual(await made.fire("user_bash", { command: "true" }, ctx), undefined);
  });

  test("project trust fallback denies session trust for exact --whitebox", async () => {
    const made = makeFakePi();
    const { deps } = fakeDependencies(["--whitebox"]);
    createWhiteboxExtension(deps)(made.pi as any);
    const result = await made.fire("project_trust", { cwd: "/tmp/project" }, fakeContext().ctx);
    assert.deepEqual(result, { trusted: "no", remember: false });
  });

  test("strict mode registers its owned tool, removes shell routes, and blocks user Bash", async () => {
    const made = makeFakePi({ active: ["read", "bash", "vendor.bash", "edit"] });
    const { deps, cleaned } = fakeDependencies(["--no-approve", "--whitebox"]);
    createWhiteboxExtension(deps)(made.pi as any);
    const { ctx } = fakeContext(false);
    await made.fire("session_start", { reason: "startup" }, ctx);
    assert.deepEqual(made.activeTools, ["read", "edit", "whitebox_run"]);
    assert.equal(made.toolDefinition?.name, "whitebox_run");
    assert.equal(made.toolDefinition?.executionMode, "sequential");
    const toolResult = await made.toolDefinition.execute("call-1", { command: "printf ok" }, undefined, undefined, ctx);
    assert.match(toolResult.content[0].text, /termination=exit/);
    assert.match(toolResult.content[0].text, /network=isolated/);
    assert.match(
      (await made.fire("tool_call", { toolName: "bash", input: { command: "true" } }, ctx)).reason,
      /disabled/,
    );
    const userBash = await made.fire("user_bash", { command: "true" }, ctx);
    assert.equal(userBash.result.exitCode, 126);
    const readMetadata = made.tools.find((tool) => tool.name === "read")!;
    readMetadata.sourceInfo = { path: "/other.ts", source: "local" };
    const blockedRead = await made.fire("tool_call", { toolName: "read", input: { path: "source.txt" } }, ctx);
    assert.match(blockedRead.reason, /ownership/);
    await made.fire("session_shutdown", { reason: "quit" }, ctx);
    assert.equal(cleaned.length, 1);
  });

  test("same-session tool calls cannot overlap", async () => {
    const made = makeFakePi();
    let calls = 0;
    let release: ((result: SandboxRunResult) => void) | undefined;
    const { deps } = fakeDependencies(["--no-approve", "--whitebox"], {
      runSandbox: async () => {
        calls++;
        if (calls === 1) return successfulRun();
        return new Promise<SandboxRunResult>((resolveRun) => { release = resolveRun; });
      },
    });
    createWhiteboxExtension(deps)(made.pi as any);
    const { ctx } = fakeContext(false);
    await made.fire("session_start", { reason: "startup" }, ctx);
    const first = made.toolDefinition.execute("run-1", { command: "sleep 1" }, undefined, undefined, ctx);
    await assert.rejects(
      made.toolDefinition.execute("run-2", { command: "true" }, undefined, undefined, ctx),
      /already active/,
    );
    release!(successfulRun("done"));
    await first;
    await made.fire("session_shutdown", { reason: "quit" }, ctx);
  });

  test("preflight failure keeps Bash closed and does not expose whitebox_run", async () => {
    const made = makeFakePi();
    const { deps, cleaned } = fakeDependencies(["--no-approve", "--whitebox"], {
      runSandbox: async () => ({ ...successfulRun("preflight failed"), exitCode: 1 }),
    });
    createWhiteboxExtension(deps)(made.pi as any);
    const { ctx, notifications } = fakeContext(false);
    await made.fire("session_start", { reason: "startup" }, ctx);
    assert.equal(made.toolDefinition, undefined);
    assert.equal(made.activeTools.includes("bash"), false);
    assert.equal((await made.fire("user_bash", { command: "true" }, ctx)).result.exitCode, 126);
    assert.ok(notifications.some(([message]) => message.includes("preflight failed")));
    assert.equal(cleaned.length, 1);
  });

  test("tool collision and unsafe CLI forms fail closed", async () => {
    for (const argv of [
      ["--no-approve", "--whitebox=false"],
      ["--no-approve", "--whitebox", "--whitebox=false"],
      ["--approve", "--whitebox"],
      ["--whitebox"],
    ]) {
      const made = makeFakePi({
        existingTools: argv[0] === "collision"
          ? [{ name: "whitebox_run", sourceInfo: { path: "/other.ts", source: "local" } }]
          : [],
      });
      const { deps } = fakeDependencies(argv);
      createWhiteboxExtension(deps)(made.pi as any);
      const { ctx } = fakeContext(false);
      await made.fire("session_start", { reason: "startup" }, ctx);
      assert.equal(made.activeTools.includes("bash"), false);
      assert.equal((await made.fire("user_bash", { command: "true" }, ctx)).result.exitCode, 126);
    }

    const fileCollision = makeFakePi({
      existingTools: [{
        name: "read",
        description: "other read",
        parameters: { type: "object", properties: {} },
        sourceInfo: { path: "/other-read.ts", source: "local" },
      } as any],
    });
    const fileCollisionDeps = fakeDependencies(["--no-approve", "--whitebox"]);
    createWhiteboxExtension(fileCollisionDeps.deps)(fileCollision.pi as any);
    const fileCollisionCtx = fakeContext(false).ctx;
    await fileCollision.fire("session_start", { reason: "startup" }, fileCollisionCtx);
    assert.equal(fileCollision.activeTools.includes("read"), false);
    assert.match(
      (await fileCollision.fire("tool_call", { toolName: "read", input: { path: "source.txt" } }, fileCollisionCtx)).reason,
      /ownership|readiness/,
    );

    const collision = makeFakePi({
      existingTools: [{ name: "whitebox_run", sourceInfo: { path: "/other.ts", source: "local" } }],
      active: ["read", "bash", "whitebox_run"],
    });
    const { deps } = fakeDependencies(["--no-approve", "--whitebox"]);
    createWhiteboxExtension(deps)(collision.pi as any);
    const { ctx } = fakeContext(false);
    await collision.fire("session_start", { reason: "startup" }, ctx);
    assert.equal(collision.activeTools.includes("whitebox_run"), false);
    const blocked = await collision.fire("tool_call", { toolName: "whitebox_run", input: { command: "true" } }, ctx);
    assert.match(blocked.reason, /ownership|readiness/);
  });
});

describe("actual Bubblewrap integration", () => {
  test("Pi file tools are confined to the workspace with .git and captures read-only", { timeout: 45_000 }, async () => {
    const fixture = await makeFixture("file-tools");
    const store = await createTempStore();
    try {
      const policy = await prepareTestSandbox(fixture.workspace, { homeDir: fixture.fakeHome });
      const run = (toolName: (typeof FILE_TOOL_NAMES)[number], params: Record<string, unknown>) =>
        runBoundaryFileTool(policy, { toolName, params, modelSupportsImages: false });

      const read = await run("read", { path: "@source.txt" });
      assert.equal(read.content[0].text, "original\n");
      await run("write", { path: "nested/generated.txt", content: "generated\n" });
      assert.equal(await readFile(join(fixture.workspace, "nested", "generated.txt"), "utf8"), "generated\n");
      await run("edit", {
        path: "source.txt",
        edits: [{ oldText: "original", newText: "changed" }],
      });
      assert.equal(await readFile(join(fixture.workspace, "source.txt"), "utf8"), "changed\n");
      assert.match((await run("grep", { pattern: "changed", path: "." })).content[0].text, /source\.txt:1/);
      assert.match((await run("find", { pattern: "*.txt", path: "." })).content[0].text, /source\.txt/);
      assert.match((await run("ls", { path: "." })).content[0].text, /nested\//);

      for (const path of [
        join(fixture.sibling, "secret.txt"),
        "../sibling/secret.txt",
        `@${join(fixture.sibling, "secret.txt")}`,
        pathToFileURL(join(fixture.sibling, "secret.txt")).href,
      ]) {
        await assert.rejects(() => run("read", { path }), /outside the workspace/);
        await assert.rejects(() => run("write", { path, content: "stolen" }), /outside the workspace/);
      }
      await assert.rejects(() => run("read", { path: "escape-link" }), /follow a path outside/);
      await assert.rejects(() => run("write", { path: "escape-link", content: "stolen" }), /follow a path outside/);
      await assert.rejects(() => run("grep", { pattern: "host-secret", path: "escape-link" }), /follow a path outside/);
      await assert.rejects(() => run("find", { pattern: "*", path: "escape-link" }), /follow a path outside/);
      await assert.rejects(() => run("ls", { path: fixture.sibling }), /outside the workspace/);
      await symlink(fixture.sibling, join(fixture.workspace, "escape-dir"));
      await assert.rejects(
        () => run("write", { path: "escape-dir/new.txt", content: "stolen" }),
        /follow a path outside/,
      );
      await assert.rejects(() => access(join(fixture.sibling, "new.txt")));

      const gitRead = await run("read", { path: ".git/config" });
      assert.match(gitRead.content[0].text, /^\[core\]/);
      await assert.rejects(
        () => run("write", { path: ".git/blocked", content: "no" }),
        /cannot modify \.git/,
      );
      await assert.rejects(
        () => run("edit", { path: ".git/config", edits: [{ oldText: "core", newText: "bad" }] }),
        /cannot modify \.git/,
      );

      const workspaceControlPath = join(fixture.workspace, "workspace-control.txt");
      await writeFile(workspaceControlPath, "workspace \u202e unchanged\n");
      const workspaceControl = await run("read", { path: "workspace-control.txt" });
      assert.equal(workspaceControl.content[0].text, "workspace \u202e unchanged\n");

      const capturePath = join(store.root, `output-${randomUUID()}.log`);
      const rawCapture = "ansi\u001b[31mred\u001b]0;title\u0007 bidi\u202ereversed isolate\u2066text c1\u0085\n";
      await writeFile(capturePath, rawCapture, { mode: 0o600 });
      const capture = await registerCapture(store, capturePath);
      const captureRequest = (toolName: "read" | "grep", params: Record<string, unknown>) =>
        runBoundaryFileTool(policy, {
          toolName,
          params: { path: capturePath, ...params },
          modelSupportsImages: false,
          captures: [capture],
        });
      const captured = await captureRequest("read", {});
      const capturedGrep = await captureRequest("grep", { pattern: "reversed" });
      for (const result of [captured, capturedGrep]) {
        assert.doesNotMatch(
          result.content[0].text,
          /[\u0000-\u0008\u000b-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/,
        );
      }
      await assert.rejects(
        () => runBoundaryFileTool(policy, {
          toolName: "write",
          params: { path: capturePath, content: "changed" },
          modelSupportsImages: false,
          captures: [capture],
        }),
        /outside the workspace/,
      );
      assert.equal(await readFile(capturePath, "utf8"), rawCapture);
      await rm(capturePath);
      await writeFile(capturePath, "replacement\n", { mode: 0o600 });
      await assert.rejects(
        () => runBoundaryFileTool(policy, {
          toolName: "read",
          params: { path: capturePath },
          modelSupportsImages: false,
          captures: [capture],
        }),
        /capture ownership changed/,
      );
    } finally {
      await cleanupTempStore(store);
      await rm(fixture.root, { recursive: true, force: true });
    }
  });

  test("file workers have a parent-enforced deadline", { timeout: 10_000 }, async () => {
    const fixture = await makeFixture("file-timeout");
    try {
      const policy = await prepareTestSandbox(fixture.workspace, { homeDir: fixture.fakeHome });
      const hangingWorker = join(fixture.root, "hanging-worker");
      await writeFile(hangingWorker, "#!/bin/sh\nexec sleep 30\n");
      await chmod(hangingWorker, 0o755);
      const started = Date.now();
      await assert.rejects(
        () => runBoundaryFileTool(
          { ...policy, flockPath: hangingWorker },
          { toolName: "read", params: { path: "source.txt" }, modelSupportsImages: false },
          undefined,
          0.1,
        ),
        /timed out after 0.1 seconds/,
      );
      assert.ok(Date.now() - started < 2_000);
    } finally {
      await rm(fixture.root, { recursive: true, force: true });
    }
  });

  test("filesystem, environment, network, namespace, and runtime boundaries hold", { timeout: 30_000 }, async () => {
    const fixture = await makeFixture("boundary");
    const store = await createTempStore();
    try {
      const policy = await prepareTestSandbox(fixture.workspace, {
        homeDir: fixture.fakeHome,
        agentDir: join(fixture.fakeHome, ".pi", "agent"),
      });
      const hostNetNamespace = await readlink("/proc/self/ns/net");
      const hostPidNamespace = await readlink("/proc/self/ns/pid");
      const hostIpcNamespace = await readlink("/proc/self/ns/ipc");
      const hostUtsNamespace = await readlink("/proc/self/ns/uts");
      const hostUserNamespace = await readlink("/proc/self/ns/user");
      const command = `set -eu
printf 'changed\\n' > generated.txt
[ "$(cat .git/config | head -n 1)" = "[core]" ]
if touch .git/blocked 2>/tmp/git-write.err; then exit 41; fi
if cat escape-link >/tmp/escape.out 2>/tmp/escape.err; then exit 42; fi
if cat ${fixture.fakeHome}/credential.txt >/tmp/home.out 2>/tmp/home.err; then exit 43; fi
if touch /usr/whitebox-write-test 2>/tmp/usr-write.err; then exit 44; fi
if touch /opt/node/whitebox-write-test 2>/tmp/node-write.err; then exit 47; fi
if touch /whitebox-root-write-test 2>/tmp/root-write.err; then exit 48; fi
[ -z "\${PI_MODEL-}" ] && [ -z "\${PI_SESSION_FILE-}" ] && [ -z "\${SSH_AUTH_SOCK-}" ]
[ "$PWD" = /workspace ] && [ "$HOME" = /home/whitebox ]
[ "$(id -u)" = "${process.getuid?.() ?? 1000}" ]
[ "$(readlink /proc/self/ns/net)" != "${hostNetNamespace}" ]
[ "$(readlink /proc/self/ns/pid)" != "${hostPidNamespace}" ]
[ "$(readlink /proc/self/ns/ipc)" != "${hostIpcNamespace}" ]
[ "$(readlink /proc/self/ns/uts)" != "${hostUtsNamespace}" ]
[ "$(readlink /proc/self/ns/user)" != "${hostUserNamespace}" ]
[ "$(hostname)" = whitebox ]
grep -q '^CapEff:[[:space:]]*0000000000000000$' /proc/self/status
grep -q '^CapBnd:[[:space:]]*0000000000000000$' /proc/self/status
grep -q '^NoNewPrivs:[[:space:]]*1$' /proc/self/status
if unshare --user true >/tmp/userns.out 2>/tmp/userns.err; then exit 46; fi
[ ! -e /proc/${process.pid} ]
printf ok >/tmp/tmp-write
printf ok >/home/whitebox/home-write
printf ok >/run/run-write
python3 - <<'PY'
import os
for path, limit in [("/tmp", ${TMP_SIZE_BYTES}), ("/home", ${HOME_SIZE_BYTES}), ("/run", ${RUN_SIZE_BYTES})]:
    stat = os.statvfs(path)
    size = stat.f_frsize * stat.f_blocks
    if size > limit:
        raise SystemExit(f"{path} tmpfs too large: {size} > {limit}")
PY
node --version
npm --version
npx --version
[ ! -e /opt/node/README.md ]
[ ! -e /opt/node/lib/node_modules/corepack ]
[ -r /opt/node/lib/node_modules/@earendil-works/pi-coding-agent/dist/index.js ]
if npm view whitebox-offline-probe-package-019ff6 >/tmp/npm-view.out 2>/tmp/npm-view.err; then exit 45; fi
python3 --version
git status --short
cat >/tmp/Makefile <<'MAKE'
all:
\tprintf 'int main(void){return 0;}\\n' > /tmp/whitebox.c
\tcc /tmp/whitebox.c -o /tmp/whitebox-bin
MAKE
make -f /tmp/Makefile >/dev/null
/tmp/whitebox-bin
cat >/tmp/whitebox-addon.cc <<'CPP'
#include <node_api.h>
napi_value Init(napi_env env, napi_value exports) {
  napi_value value;
  napi_create_string_utf8(env, "native-ok", NAPI_AUTO_LENGTH, &value);
  napi_set_named_property(env, exports, "status", value);
  return exports;
}
NAPI_MODULE(NODE_GYP_MODULE_NAME, Init)
CPP
c++ -shared -fPIC -DNODE_GYP_MODULE_NAME=whitebox_addon -I/opt/node/include/node /tmp/whitebox-addon.cc -o /tmp/whitebox-addon.node
node -e "if (require('/tmp/whitebox-addon.node').status !== 'native-ok') process.exit(1)"
python3 - <<'PY'
import socket
s = socket.socket()
s.settimeout(1)
try:
    s.connect(("1.1.1.1", 53))
except OSError:
    print("network-blocked")
else:
    raise SystemExit("network unexpectedly reachable")
finally:
    s.close()
PY
printf 'BOUNDARY_OK\\n'`;
      const result = await runSandbox(policy, {
        command,
        timeoutSeconds: 20,
        tempStore: store,
      });
      assert.equal(result.termination, "exit", result.output.content);
      assert.equal(result.exitCode, 0, result.output.content);
      assert.match(result.output.content, /network-blocked/);
      assert.match(result.output.content, /BOUNDARY_OK/);
      assert.equal(await readFile(join(fixture.workspace, "generated.txt"), "utf8"), "changed\n");
      await assert.rejects(() => access(join(fixture.workspace, ".git", "blocked")));
      assert.match(policySummary(policy, 20), /network=isolated/);
    } finally {
      await cleanupTempStore(store);
      await rm(fixture.root, { recursive: true, force: true });
    }
  });

  test("nonzero status, lock contention, timeout descendants, output cap, and cleanup are observable", { timeout: 30_000 }, async () => {
    const fixture = await makeFixture("lifecycle");
    const store = await createTempStore();
    try {
      assert.equal((await stat(store.root)).mode & 0o777, 0o700);
      const policy = await prepareTestSandbox(fixture.workspace, { homeDir: fixture.fakeHome });

      const nonzero = await runSandbox(policy, {
        command: "printf 'expected failure\\n'; exit 7",
        timeoutSeconds: 5,
        tempStore: store,
      });
      assert.equal(nonzero.termination, "exit");
      assert.equal(nonzero.exitCode, 7);
      assert.match(nonzero.output.content, /expected failure/);

      const exit75 = await runSandbox(policy, {
        command: `exit ${LOCK_CONFLICT_EXIT_CODE}`,
        timeoutSeconds: 5,
        tempStore: store,
      });
      assert.equal(exit75.termination, "exit");
      assert.equal(exit75.exitCode, LOCK_CONFLICT_EXIT_CODE);

      const controlled = await runSandbox(policy, {
        command: "printf '\\033[31mred'",
        timeoutSeconds: 5,
        tempStore: store,
      });
      assert.equal(controlled.output.sanitized, true);
      assert.match(controlled.output.content, /^\?\[31mred$/);
      assert.ok(controlled.capturedOutputPath);

      const lockController = new AbortController();
      const readyPath = join(fixture.workspace, ".whitebox-lock-ready");
      const first = runSandbox(policy, {
        command: "printf ready > .whitebox-lock-ready; exec sleep 30",
        timeoutSeconds: 30,
        signal: lockController.signal,
        tempStore: store,
      });
      await eventually(async () => {
        try {
          return (await readFile(readyPath, "utf8")) === "ready";
        } catch {
          return false;
        }
      });
      const second = await runSandbox(policy, {
        command: "true",
        timeoutSeconds: 5,
        tempStore: store,
      });
      assert.equal(second.termination, "lock_conflict");
      assert.equal(second.exitCode, LOCK_CONFLICT_EXIT_CODE);
      lockController.abort();
      const firstResult = await first;
      assert.equal(firstResult.termination, "aborted");

      const marker = `whitebox-child-${randomUUID()}`;
      const timed = await runSandbox(policy, {
        command: `node -e 'setTimeout(() => {}, 30000)' ${marker} & wait`,
        timeoutSeconds: 1,
        tempStore: store,
      });
      assert.equal(timed.termination, "timeout");
      await eventually(async () => !(await processWithMarkerExists(marker)));

      const capped = await runSandbox(policy, {
        command: "python3 -c 'import sys; sys.stdout.write(\"x\" * 8192); sys.stdout.flush()'",
        timeoutSeconds: 5,
        maxCaptureBytes: 4_096,
        tempStore: store,
      });
      assert.equal(capped.termination, "output_limit");
      assert.equal(capped.capturedBytes, 4_096);
      assert.ok(capped.observedBytes > 4_096);
      assert.ok(capped.capturedOutputPath);
      const capturedStat = await stat(capped.capturedOutputPath!);
      assert.equal(capturedStat.size, 4_096);
      assert.equal(capturedStat.mode & 0o777, 0o600);
      const priorCapture = capped.capturedOutputPath!;
      const replacement = await runSandbox(policy, {
        command: "python3 -c 'import sys; sys.stdout.write(\"y\" * 8192); sys.stdout.flush()'",
        timeoutSeconds: 5,
        maxCaptureBytes: 4_096,
        tempStore: store,
      });
      assert.ok(replacement.capturedOutputPath);
      assert.notEqual(replacement.capturedOutputPath, priorCapture);
      await assert.rejects(() => access(priorCapture));
    } finally {
      await cleanupTempStore(store);
      assert.equal(await assertTempStoreRemoved(store), true);
      await rm(fixture.root, { recursive: true, force: true });
    }
  });
});

type RpcResult = {
  response: any;
  events: any[];
  stderr: string;
  probe?: any;
};

async function runRpcProbe(options: {
  fixture: Awaited<ReturnType<typeof makeFixture>>;
  strict: boolean;
  reactivateBash?: boolean;
  reload?: boolean;
  beforeCandidateExtensions?: string[];
}): Promise<RpcResult> {
  const probePath = join(options.fixture.root, "probe.ts");
  const probeOutput = join(options.fixture.root, "probe.json");
  const canaryDir = join(options.fixture.workspace, ".pi", "extensions", "canary");
  const canaryMarker = join(options.fixture.root, "project-canary-ran");
  await mkdir(canaryDir, { recursive: true });
  await writeFile(
    join(canaryDir, "index.ts"),
    `import { writeFileSync } from "node:fs";\nwriteFileSync(${JSON.stringify(canaryMarker)}, "ran");\nexport default function() {}\n`,
  );
  await writeFile(
    probePath,
    `import { readFileSync, writeFileSync } from "node:fs";
export default function(pi) {
  pi.on("session_start", (_event, ctx) => {
    ${options.reactivateBash ? 'pi.setActiveTools([...new Set([...pi.getActiveTools(), "bash"])]);' : ""}
    let generation = 0;
    try { generation = JSON.parse(readFileSync(${JSON.stringify(probeOutput)}, "utf8")).generation ?? 0; } catch {}
    writeFileSync(${JSON.stringify(probeOutput)}, JSON.stringify({
      generation: generation + 1,
      active: pi.getActiveTools(),
      tools: pi.getAllTools().map((tool) => ({ name: tool.name, path: tool.sourceInfo?.path, source: tool.sourceInfo?.source })),
      trusted: ctx.isProjectTrusted(),
    }));
  });
  pi.registerCommand("whitebox-probe-reload", {
    description: "Reload the controlled Whitebox probe",
    handler: async (_args, ctx) => { await ctx.reload(); },
  });
}
`,
  );

  const args = [
    "--mode", "rpc",
    "--no-session",
    "--offline",
    "--no-context-files",
    "--no-skills",
    "--no-prompt-templates",
    "--no-themes",
    "--no-extensions",
    ...(options.beforeCandidateExtensions ?? []).flatMap((path) => ["-e", path]),
    "-e", INDEX_PATH,
    "-e", probePath,
    ...(options.strict ? ["--no-approve", "--whitebox"] : []),
  ];
  const child = spawn("pi", args, {
    cwd: options.fixture.workspace,
    env: {
      ...process.env,
      PI_OFFLINE: "1",
      [PI_PACKAGE_ROOT_ENV]: TEST_PI_PACKAGE_ROOT,
    },
    stdio: ["pipe", "pipe", "pipe"],
  });
  let stdout = "";
  let stderr = "";
  const events: any[] = [];
  let response: any;
  let reloadResponse: any;
  child.stdout.on("data", (chunk) => {
    stdout += chunk.toString("utf8");
    while (true) {
      const newline = stdout.indexOf("\n");
      if (newline < 0) break;
      const line = stdout.slice(0, newline);
      stdout = stdout.slice(newline + 1);
      if (!line.trim()) continue;
      const event = JSON.parse(line);
      events.push(event);
      if (event.type === "response" && event.id === "bash-probe") response = event;
      if (event.type === "response" && event.id === "reload-probe") reloadResponse = event;
    }
  });
  child.stderr.on("data", (chunk) => {
    stderr += chunk.toString("utf8");
  });

  try {
    await eventually(async () => {
      try {
        await access(probeOutput);
        return true;
      } catch {
        return false;
      }
    }, 15_000);
    if (options.reload) {
      child.stdin.write(`${JSON.stringify({ id: "reload-probe", type: "prompt", message: "/whitebox-probe-reload" })}\n`);
      await eventually(async () => reloadResponse !== undefined, 15_000);
      assert.equal(reloadResponse.success, true);
      await eventually(async () => {
        try {
          return JSON.parse(await readFile(probeOutput, "utf8")).generation >= 2;
        } catch {
          return false;
        }
      }, 15_000);
    }
    child.stdin.write(`${JSON.stringify({ id: "bash-probe", type: "bash", command: "printf RPC_HOST_BASH_RAN" })}\n`);
    await eventually(async () => response !== undefined, 10_000);
    const probe = JSON.parse(await readFile(probeOutput, "utf8"));
    await assert.rejects(() => access(canaryMarker));
    return { response, events, stderr, probe };
  } finally {
    child.kill("SIGTERM");
    await new Promise<void>((resolveExit) => {
      const timer = setTimeout(() => {
        child.kill("SIGKILL");
        resolveExit();
      }, 3_000);
      child.once("exit", () => {
        clearTimeout(timer);
        resolveExit();
      });
    });
  }
}

describe("actual Pi entry point", () => {
  test("an actual AgentSession enforces Whitebox command and file tools without a provider call", { timeout: 60_000 }, async () => {
    const fixture = await makeFixture("pi-sdk-tool");
    let session: any;
    try {
      const nodeRoot = await findNodeDistributionRoot(process.execPath);
      const sdkUrl = pathToFileURL(
        join(nodeRoot, "lib", "node_modules", "@earendil-works", "pi-coding-agent", "dist", "index.js"),
      ).href;
      const sdk: any = await import(sdkUrl);
      const settings = sdk.SettingsManager.inMemory({});
      settings.setProjectTrusted(false);
      const loader = new sdk.DefaultResourceLoader({
        cwd: fixture.workspace,
        agentDir: join(fixture.root, "sdk-agent"),
        settingsManager: settings,
        noExtensions: true,
        noSkills: true,
        noPromptTemplates: true,
        noThemes: true,
        noContextFiles: true,
        extensionFactories: [{
          name: "whitebox-sdk-test",
          factory: createWhiteboxExtension({
            argv: ["--no-approve", "--whitebox"],
            prepareSandbox: (cwd) => prepareTestSandbox(cwd),
          }),
        }],
      });
      await loader.reload();
      ({ session } = await sdk.createAgentSession({
        cwd: fixture.workspace,
        agentDir: join(fixture.root, "sdk-agent"),
        resourceLoader: loader,
        settingsManager: settings,
        sessionManager: sdk.SessionManager.inMemory(fixture.workspace),
      }));
      await session.bindExtensions({});
      assert.ok(session.getActiveToolNames().includes("whitebox_run"));
      assert.equal(session.getActiveToolNames().includes("bash"), false);
      const allTools = session.getAllTools();
      const whiteboxSource = allTools.find((candidate: any) => candidate.name === "whitebox_run")?.sourceInfo?.path;
      assert.ok(whiteboxSource);
      for (const name of FILE_TOOL_NAMES) {
        assert.equal(allTools.find((candidate: any) => candidate.name === name)?.sourceInfo?.path, whiteboxSource);
      }

      const readTool = session.agent.state.tools.find((candidate: any) => candidate.name === "read");
      const writeTool = session.agent.state.tools.find((candidate: any) => candidate.name === "write");
      assert.ok(readTool && writeTool);
      assert.equal((await readTool.execute("sdk-read", { path: "source.txt" })).content[0].text, "original\n");
      await assert.rejects(
        readTool.execute("sdk-read-outside", { path: join(fixture.sibling, "secret.txt") }),
        /outside the workspace/,
      );
      await writeTool.execute("sdk-write", { path: "sdk-generated.txt", content: "sdk\n" });
      assert.equal(await readFile(join(fixture.workspace, "sdk-generated.txt"), "utf8"), "sdk\n");
      await assert.rejects(
        writeTool.execute("sdk-write-git", { path: ".git/blocked", content: "no" }),
        /cannot modify \.git/,
      );

      const tool = session.agent.state.tools.find((candidate: any) => candidate.name === "whitebox_run");
      assert.ok(tool);
      const validation: any = await import(pathToFileURL(join(
        nodeRoot, "lib", "node_modules", "@earendil-works", "pi-coding-agent", "node_modules",
        "@earendil-works", "pi-ai", "dist", "utils", "validation.js",
      )).href);
      assert.deepEqual(validation.validateToolArguments(tool, {
        id: "validate-ok", name: "whitebox_run", arguments: { command: "true", timeout: 5 },
      }), { command: "true", timeout: 5 });
      assert.throws(() => validation.validateToolArguments(tool, {
        id: "validate-bad", name: "whitebox_run",
        arguments: { command: "true", timeout: MAX_TIMEOUT_SECONDS + 1 },
      }), /Validation failed/);
      const result = await tool.execute("sdk-call", { command: "printf SDK_TOOL_OK" }, undefined, undefined);
      assert.match(result.content[0].text, /SDK_TOOL_OK/);
      assert.match(result.content[0].text, /network=isolated/);

      const capturedRun = await tool.execute(
        "sdk-capture",
        { command: "printf '\\033[31mcaptured'" },
        undefined,
        undefined,
      );
      const capturedPath = capturedRun.details.capturedOutputPath;
      assert.ok(capturedPath);
      assert.match((await readTool.execute("sdk-read-capture", { path: capturedPath })).content[0].text, /captured/);
      await assert.rejects(
        writeTool.execute("sdk-write-capture", { path: capturedPath, content: "changed" }),
        /outside the workspace/,
      );
      const replacementCaptureRun = await tool.execute(
        "sdk-capture-replacement",
        { command: "printf '\\033[32mreplacement'" },
        undefined,
        undefined,
      );
      const replacementCapturePath = replacementCaptureRun.details.capturedOutputPath;
      assert.ok(replacementCapturePath);
      assert.notEqual(replacementCapturePath, capturedPath);
      assert.match(replacementCaptureRun.content[0].text, /replaces the previous Whitebox capture/);
      await assert.rejects(readTool.execute("sdk-read-old-capture", { path: capturedPath }), /outside the workspace/);
      assert.match(
        (await readTool.execute("sdk-read-new-capture", { path: replacementCapturePath })).content[0].text,
        /replacement/,
      );

      const cancelMarker = `whitebox-sdk-cancel-${randomUUID()}`;
      const cancelController = new AbortController();
      const cancelled = tool.execute(
        "sdk-cancel",
        { command: `node -e 'setTimeout(() => {}, 30000)' ${cancelMarker} & wait` },
        cancelController.signal,
        undefined,
      );
      setTimeout(() => cancelController.abort(), 200).unref?.();
      await assert.rejects(cancelled, /termination=aborted/);
      await eventually(async () => !(await processWithMarkerExists(cancelMarker)));
      await assert.rejects(
        tool.execute("sdk-nonzero", { command: "printf SDK_FAIL; exit 7" }, undefined, undefined),
        /exit=7/,
      );

      session.setActiveToolsByName([...session.getActiveToolNames(), "bash"]);
      const blocked = await session.extensionRunner.emitToolCall({
        type: "tool_call",
        toolName: "bash",
        toolCallId: "sdk-bash",
        input: { command: "printf SDK_HOST_BASH_MUST_NOT_RUN" },
      });
      assert.equal(blocked.block, true);
      assert.match(blocked.reason, /disabled/);
    } finally {
      if (session) {
        await session.extensionRunner.emit({ type: "session_shutdown", reason: "quit" });
        session.dispose();
      }
      await rm(fixture.root, { recursive: true, force: true });
    }
  });

  test("inactive and strict modes differ only when explicitly requested", { timeout: 45_000 }, async () => {
    const fixture = await makeFixture("pi-entry-isolated");
    try {
      const inactive = await runRpcProbe({ fixture, strict: false });
      assert.ok(inactive.probe.active.includes("bash"));
      assert.equal(inactive.probe.active.includes("whitebox_run"), false);
      assert.equal(inactive.probe.trusted, false);
      assert.equal(inactive.response.data.exitCode, 0);
      assert.match(inactive.response.data.output, /RPC_HOST_BASH_RAN/);

      const strict = await runRpcProbe({ fixture, strict: true, reactivateBash: true, reload: true });
      assert.ok(strict.probe.generation >= 2);
      assert.ok(strict.probe.active.includes("whitebox_run"));
      assert.equal(strict.probe.trusted, false);
      assert.ok(strict.probe.active.includes("bash"), "probe deliberately reactivated bash after Whitebox startup");
      const owned = strict.probe.tools.find((tool: any) => tool.name === "whitebox_run");
      assert.equal(owned.path, INDEX_PATH);
      for (const name of FILE_TOOL_NAMES) {
        assert.equal(strict.probe.tools.find((tool: any) => tool.name === name)?.path, INDEX_PATH);
      }
      assert.equal(strict.response.data.exitCode, 126);
      assert.match(strict.response.data.output, /disabled in Whitebox strict mode/);
    } finally {
      await rm(fixture.root, { recursive: true, force: true });
    }
  });

  test("actual preflight failure exposes neither host Bash nor whitebox_run", { timeout: 45_000 }, async () => {
    const fixture = await makeFixture("pi-entry-failed");
    try {
      await rm(join(fixture.workspace, ".git"), { recursive: true, force: true });
      const failed = await runRpcProbe({ fixture, strict: true });
      assert.equal(failed.probe.active.includes("bash"), false);
      assert.equal(failed.probe.active.includes("whitebox_run"), false);
      assert.equal(failed.response.data.exitCode, 126);
      assert.match(failed.response.data.output, /not ready/);
      assert.equal(failed.events.some((event) => event.type === "extension_error"), false, failed.stderr);
    } finally {
      await rm(fixture.root, { recursive: true, force: true });
    }
  });

  test("an earlier user_bash observer does not prevent strict blocking", { timeout: 45_000 }, async () => {
    const fixture = await makeFixture("pi-entry-user-bash-order");
    const observer = join(fixture.root, "earlier-user-bash.ts");
    try {
      await writeFile(
        observer,
        `export default function(pi) {
  pi.on("user_bash", () => undefined);
}\n`,
      );
      const strict = await runRpcProbe({
        fixture,
        strict: true,
        beforeCandidateExtensions: [observer],
      });
      assert.equal(strict.response.data.exitCode, 126);
      assert.match(strict.response.data.output, /Whitebox strict mode/);
    } finally {
      await rm(fixture.root, { recursive: true, force: true });
    }
  });
});
