import { accessSync, constants as fsConstants, readFileSync, realpathSync, statSync } from "node:fs";
import { delimiter, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";

export const PI_PACKAGE_ROOT_ENV = "PI_WHITEBOX_PI_PACKAGE_ROOT";
export const PI_PACKAGE_NAME = "@earendil-works/pi-coding-agent";
export const TESTED_PI_VERSIONS = Object.freeze(["0.84.2", "0.84.3"]);
const TESTED_PI_VERSION_SET = new Set(TESTED_PI_VERSIONS);

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

    for (
      let packageRoot = dirname(entrypoint);
      packageRoot !== dirname(packageRoot);
      packageRoot = dirname(packageRoot)
    ) {
      let manifest;
      try {
        manifest = JSON.parse(readFileSync(join(packageRoot, "package.json"), "utf8"));
      } catch {
        continue;
      }
      if (manifest?.name !== PI_PACKAGE_NAME) continue;
      const declaredBin = typeof manifest.bin === "string" ? manifest.bin : manifest.bin?.pi;
      if (typeof declaredBin !== "string" || !declaredBin) continue;
      const declaredPath = resolve(packageRoot, declaredBin);
      if (!isWithin(packageRoot, declaredPath)) continue;
      let canonicalDeclaredPath;
      try {
        canonicalDeclaredPath = realpathSync(declaredPath);
      } catch {
        continue;
      }
      if (canonicalDeclaredPath !== entrypoint) continue;
      if (typeof manifest.version !== "string" || !TESTED_PI_VERSION_SET.has(manifest.version)) {
        return Object.freeze({ unsupportedVersion: String(manifest.version) });
      }
      return Object.freeze({ entrypoint, packageRoot, version: manifest.version });
    }
    return undefined;
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
  const unsupportedVersions = new Set();
  for (const candidate of candidates) {
    const runtime = piRuntime(candidate);
    if (!runtime) continue;
    if ("unsupportedVersion" in runtime) {
      unsupportedVersions.add(runtime.unsupportedVersion);
      continue;
    }
    if (checked.has(runtime.entrypoint)) continue;
    checked.add(runtime.entrypoint);
    if (pathsOverlap(workspace, runtime.packageRoot)) continue;
    return runtime;
  }

  if (unsupportedVersions.size > 0) {
    throw new Error(
      `Whitebox has not been validated with Pi ${[...unsupportedVersions].join(", ")}. ` +
        `Supported: ${TESTED_PI_VERSIONS.join(", ")}.`,
    );
  }
  throw new Error("could not find an executable Pi package outside the current workspace");
}

export function resolvePiEntrypoint(options = {}) {
  return resolvePiRuntime(options).entrypoint;
}
