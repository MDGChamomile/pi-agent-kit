#!/usr/bin/env node

import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { resolvePiEntrypoint } from "./resolve-pi.mjs";

const extensionPath = fileURLToPath(new URL("../index.ts", import.meta.url));
const args = [
  "--no-extensions",
  "-e",
  extensionPath,
  "--no-skills",
  "--no-approve",
  "--whitebox",
  ...process.argv.slice(2),
];

let piEntrypoint;
try {
  piEntrypoint = resolvePiEntrypoint();
} catch (error) {
  console.error(`piw could not start Pi: ${error.message}`);
  process.exitCode = 127;
}

if (piEntrypoint) {
  // Use the Node executable that already launched piw instead of resolving a
  // second interpreter or Pi executable through a project-influenced PATH.
  const child = spawn(process.execPath, [piEntrypoint, ...args], {
    env: process.env,
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
