#!/usr/bin/env node

import { link, lstat, realpath, unlink } from "node:fs/promises";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export async function publishPlan(pendingPath, finalPath, { createFinal = link, removePending = unlink } = {}) {
  const pending = resolve(pendingPath);
  const final = resolve(finalPath);
  if (dirname(pending) !== dirname(final)) {
    throw new Error("pending and final PLAN files must be in the same record directory");
  }
  if (basename(pending) !== "PLAN.pending.md" || basename(final) !== "PLAN.md") {
    throw new Error("expected PLAN.pending.md and PLAN.md publication paths");
  }

  const source = await lstat(pending).catch((error) => {
    throw new Error(`pending PLAN is unavailable: ${error.message}`);
  });
  if (!source.isFile() || source.isSymbolicLink()) {
    throw new Error("PLAN.pending.md must be a regular file, not a directory or symbolic link");
  }

  try {
    // A hard-link creation is atomic, stays on the same filesystem, and fails
    // with EEXIST instead of replacing a concurrently created PLAN.md.
    await createFinal(pending, final);
  } catch (error) {
    if (error?.code === "EEXIST") {
      throw new Error("PLAN.md already exists; existing content was preserved");
    }
    throw new Error(`atomic no-clobber PLAN publication failed: ${error.message}`);
  }

  let cleanupWarning;
  try {
    await removePending(pending);
  } catch (error) {
    // PLAN.md already points to the complete, pre-verified inode. Failure to
    // remove its pending hard-link alias cannot invalidate publication.
    cleanupWarning = `PLAN.md was published, but PLAN.pending.md could not be removed: ${error.message}`;
  }

  return Object.freeze({ pending, final, cleanupWarning });
}

async function main() {
  if (process.argv.length !== 4) {
    console.error("usage: publish-plan.mjs RECORD/PLAN.pending.md RECORD/PLAN.md");
    process.exitCode = 2;
    return;
  }
  try {
    const result = await publishPlan(process.argv[2], process.argv[3]);
    console.log(`published ${result.final}`);
    if (result.cleanupWarning) console.warn(`warning: ${result.cleanupWarning}`);
  } catch (error) {
    console.error(`could not publish PLAN.md: ${error.message}`);
    process.exitCode = 1;
  }
}

const invokedPath = process.argv[1] ? resolve(process.argv[1]) : undefined;
if (invokedPath) {
  const [invokedRealPath, moduleRealPath] = await Promise.all([
    realpath(invokedPath).catch(() => invokedPath),
    realpath(fileURLToPath(import.meta.url)),
  ]);
  if (invokedRealPath === moduleRealPath) await main();
}
