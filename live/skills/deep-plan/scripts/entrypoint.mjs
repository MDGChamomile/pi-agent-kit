import { realpath } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

/** Run main only when moduleUrl is the invoked script, including through a symlinked path. */
export async function runIfEntrypoint(moduleUrl, main) {
  const invokedPath = process.argv[1] ? resolve(process.argv[1]) : undefined;
  if (!invokedPath) return;
  const [invokedRealPath, moduleRealPath] = await Promise.all([
    realpath(invokedPath).catch(() => invokedPath),
    realpath(fileURLToPath(moduleUrl)),
  ]);
  if (invokedRealPath === moduleRealPath) await main();
}
