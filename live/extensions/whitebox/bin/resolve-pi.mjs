import { accessSync, constants as fsConstants, readFileSync, realpathSync, statSync } from "node:fs";
import { findPackageJSON } from "node:module";
import { delimiter, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { pathToFileURL } from "node:url";

export const PI_PACKAGE_ROOT_ENV = "PI_WHITEBOX_PI_PACKAGE_ROOT";
export const PI_PACKAGE_NAME = "@earendil-works/pi-coding-agent";
export const MINIMUM_PI_VERSION = "0.84.2";
export const MAXIMUM_PI_VERSION_EXCLUSIVE = "0.85.0";
export const SUPPORTED_PI_VERSION_RANGE = `>=${MINIMUM_PI_VERSION} <${MAXIMUM_PI_VERSION_EXCLUSIVE}`;
export const VALIDATED_PI_VERSIONS = Object.freeze(["0.84.2", "0.84.3"]);
/** @type {readonly string[]} */
export const KNOWN_INCOMPATIBLE_PI_VERSIONS = Object.freeze([]);
const VALIDATED_PI_VERSION_SET = new Set(VALIDATED_PI_VERSIONS);
const KNOWN_INCOMPATIBLE_PI_VERSION_SET = new Set(KNOWN_INCOMPATIBLE_PI_VERSIONS);

/** @param {string} version */
function parsePiVersion(version) {
  const match = /^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$/.exec(version);
  if (!match) return undefined;
  return {
    parts: [Number(match[1]), Number(match[2]), Number(match[3])],
    prerelease: match[4] !== undefined,
  };
}

/** @param {number[]} first @param {number[]} second */
function compareVersionParts(first, second) {
  for (let index = 0; index < first.length; index += 1) {
    if (first[index] < second[index]) return -1;
    if (first[index] > second[index]) return 1;
  }
  return 0;
}

/** @param {string} version */
export function assessPiVersion(version) {
  const parsed = parsePiVersion(version);
  const minimum = parsePiVersion(MINIMUM_PI_VERSION);
  const maximum = parsePiVersion(MAXIMUM_PI_VERSION_EXCLUSIVE);
  if (!parsed || !minimum || !maximum) {
    return Object.freeze({ allowed: false, validated: false, reason: "version is not valid semver" });
  }
  if (parsed.prerelease) {
    return Object.freeze({ allowed: false, validated: false, reason: "prerelease versions are not supported" });
  }
  if (compareVersionParts(parsed.parts, minimum.parts) < 0) {
    return Object.freeze({
      allowed: false,
      validated: false,
      reason: `version is below the minimum ${MINIMUM_PI_VERSION}`,
    });
  }
  if (compareVersionParts(parsed.parts, maximum.parts) >= 0) {
    return Object.freeze({
      allowed: false,
      validated: false,
      reason: `version is outside the supported range ${SUPPORTED_PI_VERSION_RANGE}`,
    });
  }
  if (KNOWN_INCOMPATIBLE_PI_VERSION_SET.has(version)) {
    return Object.freeze({ allowed: false, validated: false, reason: "version is known to be incompatible" });
  }
  return Object.freeze({ allowed: true, validated: VALIDATED_PI_VERSION_SET.has(version) });
}

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

    const manifestPath = findPackageJSON(pathToFileURL(entrypoint));
    if (!manifestPath) return undefined;
    const packageRoot = dirname(manifestPath);
    const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
    if (manifest?.name !== PI_PACKAGE_NAME) return undefined;

    const declaredBin = typeof manifest.bin === "string" ? manifest.bin : manifest.bin?.pi;
    if (typeof declaredBin !== "string" || !declaredBin) return undefined;
    const declaredPath = resolve(packageRoot, declaredBin);
    if (!isWithin(packageRoot, declaredPath)) return undefined;
    if (realpathSync(declaredPath) !== entrypoint) return undefined;
    if (typeof manifest.version !== "string") {
      return Object.freeze({ unsupportedVersion: String(manifest.version), reason: "package version is missing" });
    }
    const compatibility = assessPiVersion(manifest.version);
    if (!compatibility.allowed) {
      return Object.freeze({ unsupportedVersion: manifest.version, reason: compatibility.reason });
    }
    return Object.freeze({
      entrypoint,
      packageRoot,
      version: manifest.version,
      validated: compatibility.validated,
    });
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
  const unsupportedVersions = new Map();
  for (const candidate of candidates) {
    const runtime = piRuntime(candidate);
    if (!runtime) continue;
    if ("unsupportedVersion" in runtime) {
      unsupportedVersions.set(runtime.unsupportedVersion, runtime.reason);
      continue;
    }
    if (checked.has(runtime.entrypoint)) continue;
    checked.add(runtime.entrypoint);
    if (pathsOverlap(workspace, runtime.packageRoot)) continue;
    return runtime;
  }

  if (unsupportedVersions.size > 0) {
    const details = [...unsupportedVersions].map(([version, reason]) => `${version} (${reason})`).join(", ");
    throw new Error(`Whitebox cannot use Pi ${details}. Supported range: ${SUPPORTED_PI_VERSION_RANGE}.`);
  }
  throw new Error("could not find an executable Pi package outside the current workspace");
}

export function resolvePiEntrypoint(options = {}) {
  return resolvePiRuntime(options).entrypoint;
}
