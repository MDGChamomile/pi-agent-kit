import type { ExtensionContext } from "@earendil-works/pi-coding-agent";

/** Keep warnings in Pi's UI when available, and on stderr in headless modes. */
export function warn(ctx: ExtensionContext, message: string, error?: unknown): void {
  const text = `[pi-compaction-model] ${message}`;
  if (ctx.hasUI) {
    const detail = error === undefined ? "" : error instanceof Error ? error.message : String(error);
    ctx.ui.notify(detail ? `${text} ${detail}` : text, "warning");
  } else if (error === undefined) {
    console.warn(text);
  } else {
    console.warn(text, error);
  }
}
