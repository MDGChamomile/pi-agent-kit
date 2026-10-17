/** Split the provider prefix while preserving slashes within the model ID. */
export function parseModelReference(reference: string): { provider: string; modelId: string } | null {
  const separator = reference.indexOf("/");
  if (separator <= 0 || separator === reference.length - 1) return null;

  const provider = reference.slice(0, separator).trim();
  const modelId = reference.slice(separator + 1).trim();
  return provider && modelId ? { provider, modelId } : null;
}
