import { pathToFileURL } from "node:url";

const SDK_PATH = "/opt/node/lib/node_modules/@earendil-works/pi-coding-agent/dist/index.js";

type FileToolName = "read" | "write" | "edit" | "grep" | "find" | "ls";
type WorkerRequest = {
  toolName: FileToolName;
  params: Record<string, unknown>;
  modelSupportsImages: boolean;
};

async function readStdin(): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) chunks.push(Buffer.from(chunk));
  return Buffer.concat(chunks).toString("utf8");
}

// This process runs inside Bubblewrap. Reusing Pi's factories preserves the
// built-in schemas, truncation behavior, edit diffs, and result detail shapes.
async function main(): Promise<void> {
  const request = JSON.parse(await readStdin()) as WorkerRequest;
  const sdk: any = await import(pathToFileURL(SDK_PATH).href);
  const factories: Record<FileToolName, (cwd: string) => any> = {
    read: sdk.createReadTool,
    write: sdk.createWriteTool,
    edit: sdk.createEditTool,
    grep: sdk.createGrepTool,
    find: sdk.createFindTool,
    ls: sdk.createLsTool,
  };
  const factory = factories[request.toolName];
  if (!factory) throw new Error(`Unsupported Whitebox file tool: ${String(request.toolName)}`);

  const tool = factory("/workspace");
  const context = {
    model: { input: request.modelSupportsImages ? ["text", "image"] : ["text"] },
  };
  const result = await tool.execute("whitebox-file-worker", request.params, undefined, undefined, context);
  process.stdout.write(JSON.stringify({ ok: true, result }));
}

main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  process.stdout.write(JSON.stringify({ ok: false, error: message }));
  process.exitCode = 1;
});
