import { setTimeout as sleep } from "node:timers/promises";
import { compact } from "@earendil-works/pi-coding-agent";

// compact() on the minimum supported Pi version has no retry argument and
// flattens provider failures to Error messages. Keep this classifier conservative.
export function isTransientCompactionError(error: unknown): boolean {
  if (!(error instanceof Error) || error.name === "AbortError") return false;
  const message = error.message;
  // Deterministic failures take precedence over transient words/status codes.
  if (/\b(?:400|401|403|404|422)\b|aborted|cancelled|canceled|unauthorized|forbidden|authentication|invalid.?api.?key|invalid.?request|context.?length|context.?window|too many tokens|quota|billing|budget|usage.?limit|available balance|retry delay/i.test(message)) {
    return false;
  }
  return /\b(?:408|429|500|502|503|504|520|524|ECONNRESET|ETIMEDOUT|EAI_AGAIN)\b|overloaded|rate.?limit|too many requests|service.?unavailable|internal server error|fetch failed|network error|socket hang up|other side closed|connection (?:reset|lost)|\bterminated\b|stream ended (?:without|before)|timed? out/i.test(message);
}

/** At most two complete compaction attempts; no nested summarization retry. */
export async function compactWithOneRetry(
  ...args: Parameters<typeof compact>
): ReturnType<typeof compact> {
  const signal = args[5];
  signal?.throwIfAborted();
  try {
    const result = await compact(...args);
    signal?.throwIfAborted();
    return result;
  } catch (error) {
    if (signal?.aborted || !isTransientCompactionError(error)) throw error;
    await sleep(1000, undefined, { signal });
    signal?.throwIfAborted();
    // Deliberately outside the try: a second failure is returned to the hook.
    const result = await compact(...args);
    signal?.throwIfAborted();
    return result;
  }
}
