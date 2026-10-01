#!/usr/bin/env node

import { createHash } from "node:crypto";
import { realpath } from "node:fs/promises";
import { homedir } from "node:os";
import { basename, isAbsolute, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

function expandHome(value, home) {
  if (value === "~") return home;
  if (value.startsWith("~/") || (sep === "\\" && value.startsWith("~\\"))) {
    return join(home, value.slice(2));
  }
  return value;
}

/** Select a records parent without creating directories or changing any state. */
export async function resolveRecordsRoot(projectPath, { explicitRoot, env = process.env, home = homedir() } = {}) {
  if (explicitRoot !== undefined) {
    if (!explicitRoot) throw new Error("explicit records root must not be empty");
    // Preserve the existing contract: a run-specific root is used directly.
    return resolve(expandHome(explicitRoot, home));
  }

  const canonicalProject = await realpath(projectPath);
  const name = basename(canonicalProject).replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^[._-]+|[._-]+$/g, "") || "project";
  const hash = createHash("sha256").update(canonicalProject).digest("hex").slice(0, 6);
  const override = env.PI_DEEP_PLAN_RECORDS_DIR;
  const stateHome = env.XDG_STATE_HOME && isAbsolute(env.XDG_STATE_HOME)
    ? env.XDG_STATE_HOME
    : join(home, ".local", "state");
  const root = override ? resolve(expandHome(override, home)) : join(stateHome, "pi", "deep-plan", "records");
  return join(root, `${name}-${hash}`);
}

async function main() {
  if (process.argv.length < 3 || process.argv.length > 4) {
    console.error("usage: records-root.mjs PROJECT_PATH [EXPLICIT_RECORDS_ROOT]");
    process.exitCode = 2;
    return;
  }
  try {
    console.log(await resolveRecordsRoot(process.argv[2], { explicitRoot: process.argv[3] }));
  } catch (error) {
    console.error(`could not resolve records root: ${error.message}`);
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
