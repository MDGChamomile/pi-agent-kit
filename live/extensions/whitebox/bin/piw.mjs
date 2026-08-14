#!/usr/bin/env node

import { spawn } from "node:child_process";
import { realpathSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  assertTrustedPathOutsideWorkspace,
  PI_PACKAGE_ROOT_ENV,
  resolvePiRuntime,
} from "./resolve-pi.mjs";

const extensionPath = realpathSync(fileURLToPath(new URL("../index.ts", import.meta.url)));
const extensionRoot = dirname(extensionPath);
const args = [
  "--no-extensions",
  "-e",
  extensionPath,
  "--no-skills",
  "--no-approve",
  "--whitebox",
  ...process.argv.slice(2),
];

let piRuntime;
try {
  assertTrustedPathOutsideWorkspace(process.cwd(), extensionRoot, "the Whitebox extension source");
  piRuntime = resolvePiRuntime();
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`piw could not start Pi: ${message}`);
  process.exitCode = 127;
}

if (piRuntime) {
  // Use the Node executable that already launched piw instead of resolving a
  // second interpreter or Pi executable through a project-influenced PATH.
  const child = spawn(process.execPath, [piRuntime.entrypoint, ...args], {
    env: { ...process.env, [PI_PACKAGE_ROOT_ENV]: piRuntime.packageRoot },
    stdio: "inherit",
  });

  child.once("error", (error) => {
    console.error(`piw could not start Pi: ${error.message}`);
    process.exitCode = 127;
  });

  child.once("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exitCode = code ?? 1;
  });
}
