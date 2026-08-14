import { accessSync, constants as fsConstants, readFileSync, realpathSync, statSync } from "node:fs";
import { delimiter, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";

export const PI_PACKAGE_ROOT_ENV = "PI_WHITEBOX_PI_PACKAGE_ROOT";

/** @param {string} parent @param {string} child */
function isWithin(parent, child) {
  const rel = relative(parent, child);
  return rel === "" || (!rel.startsWith(`..${sep}`) && rel !== ".." && !isAbsolute(rel));
}

/** @param {string} first @param {string} second */
export function pathsOverlap(first, second) {
  return isWithin(first, second) || isWithin(second, first);
}

/**
 * @param {string} cwd
 * @param {string} trustedPath
 * @param {string} label
 */
export function assertTrustedPathOutsideWorkspace(cwd, trustedPath, label) {
  const workspace = realpathSync(cwd);
  const canonicalTrustedPath = realpathSync(trustedPath);
  if (pathsOverlap(workspace, canonicalTrustedPath)) {
    throw new Error(`current workspace and ${label} must not overlap`);
  }
  return { workspace, trustedPath: canonicalTrustedPath };
}

/** @param {string} path */
function piRuntime(path) {
  try {
    accessSync(path, fsConstants.R_OK | fsConstants.X_OK);
    const entrypoint = realpathSync(path);
    if (!statSync(entrypoint).isFile()) return undefined;
    const packageRoot = dirname(dirname(entrypoint));
    if (dirname(entrypoint) !== join(packageRoot, "dist")) return undefined;
    const manifest = JSON.parse(readFileSync(join(packageRoot, "package.json"), "utf8"));
    if (manifest.name !== "@earendil-works/pi-coding-agent") return undefined;
    return Object.freeze({ entrypoint, packageRoot });
  } catch {
    return undefined;
  }
}

export function resolvePiRuntime({
  cwd = process.cwd(),
  execPath = process.execPath,
  pathValue = process.env.PATH ?? "",
} = {}) {
  const workspace = realpathSync(cwd);
  const candidates = [
    join(dirname(execPath), "pi"),
    ...pathValue.split(delimiter).filter(Boolean).map((entry) =>
      join(isAbsolute(entry) ? entry : resolve(cwd, entry), "pi")
    ),
  ];

  const checked = new Set();
  for (const candidate of candidates) {
    const runtime = piRuntime(candidate);
    if (!runtime || checked.has(runtime.entrypoint)) continue;
    checked.add(runtime.entrypoint);
    if (pathsOverlap(workspace, runtime.packageRoot)) continue;
    return runtime;
  }

  throw new Error("could not find an executable Pi package outside the current workspace");
}

export function resolvePiEntrypoint(options = {}) {
  return resolvePiRuntime(options).entrypoint;
}
