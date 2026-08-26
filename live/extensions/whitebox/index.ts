import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import {
  FILE_TOOL_NAMES,
  isFileToolName,
  registerCapture,
  runBoundaryFileTool,
  type CaptureRecord,
  type FileToolName,
} from "./file-boundary.ts";
import {
  cleanupTempStore,
  createTempStore,
  DEFAULT_TIMEOUT_SECONDS,
  MAX_TIMEOUT_SECONDS,
  policySummary,
  prepareSandbox,
  runSandbox,
  sanitizeDisplayText,
  type SandboxPolicy,
  type SandboxRunResult,
  type TempStore,
} from "./sandbox.ts";

const TOOL_NAME = "whitebox_run";
const STATUS_KEY = "whitebox";
const PREFLIGHT_COMMAND = [
  "node --version >/dev/null",
  "npm --version >/dev/null",
  "npx --version >/dev/null",
  "python3 --version >/dev/null",
  "git --version >/dev/null",
  "rg --version >/dev/null",
  "(fd --version >/dev/null 2>&1 || fdfind --version >/dev/null 2>&1)",
  "test \"$PWD\" = /workspace",
  "test \"$HOME\" = /home/whitebox",
  "test -z \"${PI_SESSION_FILE-}\"",
  "test -r .git/config",
  "if touch .git/.whitebox-preflight 2>/tmp/whitebox-git.err; then exit 90; fi",
].join(" && ");

const TOOL_PARAMETERS = {
  type: "object",
  properties: {
    command: {
      type: "string",
      minLength: 1,
      maxLength: 100_000,
      description: "Shell command to run inside the offline Whitebox workspace",
    },
    timeout: {
      type: "integer",
      minimum: 1,
      maximum: MAX_TIMEOUT_SECONDS,
      description: `Timeout in seconds (default ${DEFAULT_TIMEOUT_SECONDS}, maximum ${MAX_TIMEOUT_SECONDS})`,
    },
  },
  required: ["command"],
  additionalProperties: false,
} as const;

type WhiteboxState = "inactive" | "checking" | "ready" | "failed" | "shutdown";

type ToolMetadata = {
  name: string;
  description?: string;
  parameters?: unknown;
  promptGuidelines?: string[];
  sourceInfo?: { path?: string; source?: string };
};

const FILE_TOOL_PROMPT_SNIPPETS: Record<FileToolName, string> = {
  read: "Read file contents",
  write: "Create or overwrite files",
  edit: "Make precise file edits with exact text replacement, including multiple disjoint edits in one call",
  grep: "Search file contents for patterns (respects .gitignore)",
  find: "Find files by glob pattern (respects .gitignore)",
  ls: "List directory contents",
};

export interface WhiteboxDependencies {
  argv: string[];
  prepareSandbox: typeof prepareSandbox;
  runSandbox: typeof runSandbox;
  createTempStore: typeof createTempStore;
  cleanupTempStore: typeof cleanupTempStore;
}

const DEFAULT_DEPENDENCIES: WhiteboxDependencies = {
  argv: process.argv.slice(2),
  prepareSandbox,
  runSandbox,
  createTempStore,
  cleanupTempStore,
};

function shellRoute(name: string): boolean {
  return name === "bash" || name.endsWith(".bash");
}

function hasArg(argv: readonly string[], ...names: string[]): boolean {
  return argv.some((arg) => names.includes(arg));
}

function displayCommand(command: string): string {
  const safe = sanitizeDisplayText(command);
  const limit = 2_048;
  if (safe.length <= limit) return safe;
  return `${safe.slice(0, 1_024)}\n… [command display truncated] …\n${safe.slice(-1_024)}`;
}

function formatOutput(result: SandboxRunResult): string {
  let text = result.output.content;
  if (!text) text = "(no output)";
  if (result.output.sanitized) {
    text += "\n\n[Control characters were replaced for display; raw captured output is retained.]";
  }
  if (result.output.truncated) {
    text += `\n\n[Output truncated: ${result.output.shownLines}/${result.output.totalLines} lines, `;
    text += `${result.output.shownBytes}/${result.output.totalBytes} bytes shown.`;
    if (result.capturedOutputPath) {
      text += ` Captured output: ${result.capturedOutputPath}.`;
      text += " Read or grep the capture only if more detail is needed.";
    }
    text += "]";
  } else if (result.capturedOutputPath) {
    text += `\n\n[Captured output: ${result.capturedOutputPath}]`;
  }
  return text;
}

function formatFinalResult(
  command: string,
  policy: SandboxPolicy,
  timeout: number,
  result: SandboxRunResult,
  captureReplaced: boolean,
): string {
  const captureNotice = captureReplaced
    ? "\n\n[This capture replaces the previous Whitebox capture.]"
    : "";
  return [
    `$ ${displayCommand(command)}`,
    formatOutput(result) + captureNotice,
    "",
    `[Whitebox: ${policySummary(policy, timeout)}; termination=${result.termination}; ` +
      `exit=${result.exitCode ?? "unknown"}; duration=${result.durationMs}ms]`,
  ].join("\n");
}

function failureMessage(reason: string): string {
  const safeReason = sanitizeDisplayText(reason);
  return `Whitebox strict mode is not ready: ${safeReason}. Host Bash remains blocked; restart without --whitebox to use normal Pi.`;
}

function currentTool(pi: ExtensionAPI, name: string): ToolMetadata | undefined {
  return (pi.getAllTools() as ToolMetadata[]).find((tool) => tool.name === name);
}

// Pi's built-in edit preview reads the target on the host before execute(). Use
// a path-only renderer so every content read still passes through Bubblewrap.
class SafeToolCallComponent {
  text = "";
  render(_width: number): string[] { return [this.text]; }
  invalidate(): void {}
}

function safeEditRenderCall(args: any, theme: any, context: any): SafeToolCallComponent {
  const component = context.lastComponent instanceof SafeToolCallComponent
    ? context.lastComponent
    : new SafeToolCallComponent();
  const path = sanitizeDisplayText(typeof args?.path === "string" ? args.path : "(invalid path)");
  component.text = `${theme.fg("toolTitle", theme.bold("edit"))} ${theme.fg("accent", path)}`;
  return component;
}

function prepareEditArguments(input: unknown): unknown {
  if (!input || typeof input !== "object") return input;
  const args = input as Record<string, unknown>;
  if (typeof args.edits === "string") {
    try {
      const parsed = JSON.parse(args.edits);
      if (Array.isArray(parsed)) args.edits = parsed;
    } catch {}
  }
  if (typeof args.oldText !== "string" || typeof args.newText !== "string") return args;
  const edits = Array.isArray(args.edits) ? [...args.edits] : [];
  edits.push({ oldText: args.oldText, newText: args.newText });
  const { oldText: _oldText, newText: _newText, ...rest } = args;
  return { ...rest, edits };
}

export function createWhiteboxExtension(
  overrides: Partial<WhiteboxDependencies> = {},
): (pi: ExtensionAPI) => void {
  const deps: WhiteboxDependencies = { ...DEFAULT_DEPENDENCIES, ...overrides };

  return function whiteboxExtension(pi: ExtensionAPI): void {
    const exactWhiteboxArg = hasArg(deps.argv, "--whitebox");
    const valuedWhiteboxArg = deps.argv.some((arg) => arg.startsWith("--whitebox="));
    const anyWhiteboxArg = exactWhiteboxArg || valuedWhiteboxArg;
    const malformedWhiteboxArg = valuedWhiteboxArg;
    const noApproveArg = hasArg(deps.argv, "--no-approve", "-na");
    const approveArg = hasArg(deps.argv, "--approve", "-a");

    let state: WhiteboxState = "inactive";
    let requested = anyWhiteboxArg;
    let failureReason: string | undefined;
    let policy: SandboxPolicy | undefined;
    let tempStore: TempStore | undefined;
    let ownToolSourcePath: string | undefined;
    let activeRunPromise: Promise<SandboxRunResult> | undefined;
    const captures = new Map<string, CaptureRecord>();
    const lifecycleController = new AbortController();

    pi.registerFlag("whitebox", {
      description: "Run explicit external commands in the strict offline Whitebox sandbox",
      type: "boolean",
      default: false,
    });

    // With --no-approve or --approve Pi applies the override directly and does not emit
    // project_trust. This handler is only a fallback for an exact --whitebox invocation
    // without either override; the supported entry point still requires --no-approve.
    pi.on("project_trust", () => {
      if (!exactWhiteboxArg) return { trusted: "undecided" as const };
      return { trusted: "no" as const, remember: false };
    });

    pi.on("tool_call", (event) => {
      if (!requested) return;
      if (shellRoute(event.toolName)) {
        return {
          block: true,
          reason: state === "ready"
            ? "Host Bash is disabled in Whitebox strict mode; use whitebox_run."
            : failureMessage(failureReason ?? "startup checks have not completed"),
        };
      }
      if (event.toolName === TOOL_NAME) {
        const source = currentTool(pi, TOOL_NAME)?.sourceInfo?.path;
        if (state !== "ready" || !ownToolSourcePath || source !== ownToolSourcePath) {
          return { block: true, reason: failureMessage("whitebox_run ownership or readiness check failed") };
        }
      }
      if (isFileToolName(event.toolName)) {
        const source = currentTool(pi, event.toolName)?.sourceInfo?.path;
        if (state !== "ready" || !ownToolSourcePath || source !== ownToolSourcePath) {
          return { block: true, reason: failureMessage(`${event.toolName} ownership or readiness check failed`) };
        }
      }
    });

    pi.on("user_bash", () => {
      if (!requested) return;
      return {
        result: {
          output: state === "ready"
            ? "User !/!! commands are disabled in Whitebox strict mode. Use whitebox_run through the agent."
            : failureMessage(failureReason ?? "startup checks have not completed"),
          exitCode: 126,
          cancelled: false,
          truncated: false,
        },
      };
    });

    const markFailed = async (ctx: ExtensionContext, error: unknown) => {
      state = "failed";
      failureReason = sanitizeDisplayText(error instanceof Error ? error.message : String(error));
      ctx.ui.setStatus(STATUS_KEY, `Whitebox: blocked (${failureReason})`);
      ctx.ui.notify(failureMessage(failureReason), "error");
      const doomedStore = tempStore;
      tempStore = undefined;
      captures.clear();
      if (doomedStore) await deps.cleanupTempStore(doomedStore);
    };

    pi.on("session_start", async (_event, ctx) => {
      requested = anyWhiteboxArg || pi.getFlag("whitebox") === true;
      if (!requested) {
        state = "inactive";
        return;
      }

      state = "checking";
      ctx.ui.setStatus(STATUS_KEY, "Whitebox: checking strict boundary");
      const initiallyActiveTools = pi.getActiveTools();
      const initiallyActiveFileTools = initiallyActiveTools.filter(isFileToolName);
      const preservedHostTools = initiallyActiveTools.filter(
        (name) => !shellRoute(name) && name !== TOOL_NAME && !isFileToolName(name),
      );
      pi.setActiveTools(preservedHostTools);

      try {
        if (malformedWhiteboxArg || !exactWhiteboxArg) {
          throw new Error("use the exact --whitebox flag without a value");
        }
        if (approveArg) throw new Error("--approve/-a cannot be combined with --whitebox");
        if (!noApproveArg) throw new Error("Whitebox requires --no-approve (or -na)");
        if (ctx.isProjectTrusted()) throw new Error("project resources are trusted in this session");
        if (currentTool(pi, TOOL_NAME)) throw new Error(`${TOOL_NAME} is already registered by another source`);
        for (const name of FILE_TOOL_NAMES) {
          const existing = currentTool(pi, name);
          if (existing && existing.sourceInfo?.source !== "builtin") {
            throw new Error(`${name} is already registered by another source`);
          }
        }

        tempStore = await deps.createTempStore();
        policy = await deps.prepareSandbox(ctx.cwd);
        const preflight = await deps.runSandbox(policy, {
          command: PREFLIGHT_COMMAND,
          timeoutSeconds: 15,
          signal: lifecycleController.signal,
          tempStore,
        });
        if (preflight.termination !== "exit" || preflight.exitCode !== 0) {
          throw new Error(
            `sandbox preflight failed (termination=${preflight.termination}, exit=${preflight.exitCode}): ` +
              preflight.output.content,
          );
        }

        // Override every built-in file route. Metadata stays compatible with Pi,
        // while execution is delegated to the workspace-confined worker.
        for (const name of FILE_TOOL_NAMES) {
          const builtin = currentTool(pi, name);
          if (!builtin?.parameters || !builtin.description) {
            throw new Error(`Pi did not provide built-in metadata for ${name}`);
          }
          const boundaryDefinition: any = {
            name,
            label: name,
            parameters: builtin.parameters,
            promptSnippet: FILE_TOOL_PROMPT_SNIPPETS[name],
            promptGuidelines: builtin.promptGuidelines ?? [],
            executionMode: "sequential",
            description: `${builtin.description} In Whitebox mode this tool is restricted to the current Git workspace; root .git is read-only.`,
            async execute(_toolCallId: string, params: Record<string, unknown>, signal: AbortSignal | undefined, _onUpdate: unknown, toolCtx: ExtensionContext) {
              if (state !== "ready" || !policy) {
                throw new Error(failureMessage(failureReason ?? "workspace file boundary is not ready"));
              }
              const source = currentTool(pi, name)?.sourceInfo?.path;
              if (!ownToolSourcePath || source !== ownToolSourcePath) {
                throw new Error(failureMessage(`${name} source ownership changed`));
              }
              const combinedSignal = signal
                ? AbortSignal.any([signal, lifecycleController.signal])
                : lifecycleController.signal;
              try {
                return await runBoundaryFileTool(policy, {
                  toolName: name,
                  params,
                  modelSupportsImages: toolCtx?.model?.input?.includes("image") ?? true,
                  captures: [...captures.values()],
                }, combinedSignal);
              } catch (error) {
                throw new Error(sanitizeDisplayText(error instanceof Error ? error.message : String(error)));
              }
            },
          };
          if (name === "edit") {
            boundaryDefinition.prepareArguments = prepareEditArguments;
            boundaryDefinition.renderCall = safeEditRenderCall;
          }
          pi.registerTool(boundaryDefinition);
        }

        pi.registerTool({
          name: TOOL_NAME,
          label: "Whitebox Run",
          executionMode: "sequential",
          description:
            "Run a command in the current Git workspace through strict Bubblewrap isolation. " +
            "The workspace may be modified, root .git is read-only, network and host credentials outside the workspace are unavailable. " +
            `Only a bounded output tail is returned inline; larger output is captured for on-demand reading. Capture is capped at 10MiB. Timeout defaults to ${DEFAULT_TIMEOUT_SECONDS}s.`,
          promptSnippet: "Run external project commands in the strict offline Whitebox sandbox",
          promptGuidelines: [
            "Use whitebox_run for test, build, and script commands in this Whitebox session; host Bash is unavailable.",
            "Do not use whitebox_run when the command needs network access, package downloads, or host credentials.",
          ],
          parameters: TOOL_PARAMETERS as never,
          async execute(_toolCallId, params: { command: string; timeout?: number }, signal, onUpdate, toolCtx) {
            if (state !== "ready" || !policy || !tempStore) {
              throw new Error(failureMessage(failureReason ?? "sandbox is not ready"));
            }
            const source = currentTool(pi, TOOL_NAME)?.sourceInfo?.path;
            if (!ownToolSourcePath || source !== ownToolSourcePath) {
              throw new Error(failureMessage("whitebox_run source ownership changed"));
            }
            if (activeRunPromise) throw new Error("Another Whitebox command is already active in this session");

            const timeout = params.timeout ?? DEFAULT_TIMEOUT_SECONDS;
            const combinedSignal = signal
              ? AbortSignal.any([signal, lifecycleController.signal])
              : lifecycleController.signal;
            let streamTail = "";
            let lastUpdateAt = 0;
            const update = (chunk: string) => {
              streamTail = (streamTail + chunk).slice(-4_096);
              const now = Date.now();
              if (!onUpdate || now - lastUpdateAt < 100) return;
              lastUpdateAt = now;
              onUpdate({
                content: [{ type: "text", text: `$ ${displayCommand(params.command)}\n${streamTail}\n\n[${policySummary(policy!, timeout)}]` }],
                details: { policy: policySummary(policy!, timeout), partial: true },
              });
            };

            toolCtx.ui.setStatus(STATUS_KEY, `Whitebox: running ≤${timeout}s · /workspace RW · .git RO · net off`);
            activeRunPromise = deps.runSandbox(policy, {
              command: params.command,
              timeoutSeconds: timeout,
              signal: combinedSignal,
              tempStore,
              onOutput: update,
            });
            let result: SandboxRunResult;
            try {
              result = await activeRunPromise;
            } catch (error) {
              const reason = sanitizeDisplayText(error instanceof Error ? error.message : String(error));
              throw new Error(`Whitebox command could not run: ${reason}`);
            } finally {
              activeRunPromise = undefined;
              if (state === "ready") {
                const hostToolNotice = preservedHostTools.length > 0
                  ? ` · ${preservedHostTools.length} host tool(s) outside boundary`
                  : "";
                toolCtx.ui.setStatus(
                  STATUS_KEY,
                  `Whitebox-owned tools: /workspace RW · .git RO · net off${hostToolNotice}`,
                );
              }
            }

            const captureReplaced = Boolean(result.capturedOutputPath && captures.size > 0);
            if (result.capturedOutputPath) {
              // runSandbox has already evicted the previous capture file. Clear
              // its authorization record before registering the replacement so
              // file retention and read authorization cannot diverge.
              captures.clear();
              const capture = await registerCapture(tempStore, result.capturedOutputPath);
              captures.set(capture.sourcePath, capture);
            }
            const text = formatFinalResult(params.command, policy, timeout, result, captureReplaced);
            if (result.termination !== "exit" || result.exitCode !== 0) throw new Error(text);
            return {
              content: [{ type: "text", text }],
              details: {
                exitCode: result.exitCode,
                termination: result.termination,
                durationMs: result.durationMs,
                capturedOutputPath: result.capturedOutputPath,
                policy: policySummary(policy, timeout),
              },
            };
          },
        });

        const registered = currentTool(pi, TOOL_NAME);
        ownToolSourcePath = registered?.sourceInfo?.path;
        if (!ownToolSourcePath) throw new Error("Pi did not report whitebox_run source ownership");
        for (const name of FILE_TOOL_NAMES) {
          if (currentTool(pi, name)?.sourceInfo?.path !== ownToolSourcePath) {
            throw new Error(`Pi did not install the Whitebox-owned ${name} override`);
          }
        }

        pi.setActiveTools([...new Set([...preservedHostTools, ...initiallyActiveFileTools, TOOL_NAME])]);
        state = "ready";
        const hostToolNotice = preservedHostTools.length > 0
          ? ` · ${preservedHostTools.length} other host-side tool(s) outside boundary`
          : "";
        ctx.ui.setStatus(
          STATUS_KEY,
          `Whitebox-owned files + commands workspace-only · .git RO · net off${hostToolNotice}`,
        );
        ctx.ui.notify(
          `Whitebox ready. ${policySummary(policy, DEFAULT_TIMEOUT_SECONDS)}. ` +
            `${preservedHostTools.length} additional active host-side tool(s) remain outside this boundary. ` +
            "The workspace can be damaged, and its contents remain visible to Pi and the model.",
          "warning",
        );
      } catch (error) {
        await markFailed(ctx, error);
      }
    });

    pi.on("session_shutdown", async (_event, ctx) => {
      state = "shutdown";
      lifecycleController.abort();
      if (activeRunPromise) await activeRunPromise.catch(() => undefined);
      const doomedStore = tempStore;
      tempStore = undefined;
      captures.clear();
      if (doomedStore) await deps.cleanupTempStore(doomedStore);
      ctx.ui.setStatus(STATUS_KEY, undefined);
    });
  };
}

export default createWhiteboxExtension();
