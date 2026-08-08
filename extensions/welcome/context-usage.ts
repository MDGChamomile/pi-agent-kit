function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function estimateInitialContextTokens(ctx: unknown): number | null {
  if (!isRecord(ctx) || typeof ctx.getSystemPrompt !== "function") {
    return null;
  }

  const prompt = ctx.getSystemPrompt();
  if (typeof prompt !== "string" || !prompt.trim()) {
    return null;
  }

  return Math.ceil(prompt.length / 4);
}
