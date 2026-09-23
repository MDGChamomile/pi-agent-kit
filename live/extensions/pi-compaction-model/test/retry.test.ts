import { expect, mock, test } from "bun:test";

let calls = 0;
let firstAttempt: () => void;
mock.module("@earendil-works/pi-coding-agent", () => ({
  compact: async () => {
    calls++;
    firstAttempt();
    throw new Error("503 Service unavailable");
  },
}));

const { compactWithOneRetry } = await import("../src/retry.js");

test("real backoff is interruptible and never starts a second attempt after abort", async () => {
  const controller = new AbortController();
  const started = new Promise<void>((resolve) => { firstAttempt = resolve; });
  const result = compactWithOneRetry(
    {} as any, {} as any, "synthetic-key", undefined, undefined, controller.signal,
  );
  const outcome = result.then(
    () => ({ name: "UnexpectedSuccess" }),
    (error: unknown) => error,
  );
  await started;
  // Let the rejection handler enter the real one-second timers/promises wait.
  await new Promise((resolve) => setTimeout(resolve, 10));
  controller.abort();
  expect(await outcome).toMatchObject({ name: "AbortError" });
  expect(calls).toBe(1);
});
