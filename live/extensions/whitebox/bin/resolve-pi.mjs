import { accessSync, constants as fsConstants, readFileSync, realpathSync, statSync } from "node:fs";
import { delimiter, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";

/** @param {string} parent @param {string} child */
function isWithin(parent, child) {
  const rel = relative(parent, child);
  return rel === "" || (!rel.startsWith(`..${sep}`) && rel !== ".." && !isAbsolute(rel));
}

/** @param {string} path */
function piEntrypoint(path) {
  try {
    accessSync(path, fsConstants.R_OK | fsConstants.X_OK);
    const canonical = realpathSync(path);
    if (!statSync(canonical).isFile()) return undefined;
    const packageRoot = dirname(dirname(canonical));
    if (dirname(canonical) !== join(packageRoot, "dist")) return undefined;
    const manifest = JSON.parse(readFileSync(join(packageRoot, "package.json"), "utf8"));
    if (manifest.name !== "@earendil-works/pi-coding-agent") return undefined;
    return canonical;
  } catch {
    return undefined;
  }
}

export function resolvePiEntrypoint({
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
    const canonical = piEntrypoint(candidate);
    if (!canonical || checked.has(canonical)) continue;
    checked.add(canonical);
    if (isWithin(workspace, canonical)) continue;
    return canonical;
  }

  throw new Error("could not find an executable Pi entry point outside the current workspace");
}
