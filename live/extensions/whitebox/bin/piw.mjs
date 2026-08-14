#!/usr/bin/env node

import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

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

const child = spawn("pi", args, {
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
