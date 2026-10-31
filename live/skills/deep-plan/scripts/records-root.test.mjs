import assert from "node:assert/strict";
import { mkdir, mkdtemp, readdir, realpath, rm, symlink } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { basename, join, resolve } from "node:path";
import { afterEach, test } from "node:test";
import { resolveRecordsRoot } from "./records-root.mjs";

const roots = [];

afterEach(async () => {
  await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })));
});

async function temporaryRoot() {
  const root = await mkdtemp(join(tmpdir(), "deep-plan-records-"));
  roots.push(root);
  return root;
}

test("default records are external state and resolution does not create files", async () => {
  const root = await temporaryRoot();
  const project = await realpath(root);
  const parent = await resolveRecordsRoot(project, { env: {}, home: root });
  assert.equal(parent, join(root, ".local", "state", "pi", "deep-plan", "records", basename(parent)));
  assert.match(basename(parent), new RegExp(`^${basename(project)}-[0-9a-f]{6}$`));
  assert.deepEqual(await readdir(root), []);
});

test("explicit root wins, then persistent override, then absolute XDG state", async () => {
  const root = await temporaryRoot();
  const env = { PI_DEEP_PLAN_RECORDS_DIR: "~/plans", XDG_STATE_HOME: join(root, "state") };
  const configured = await resolveRecordsRoot(root, { env, home: root });
  const key = basename(configured);
  assert.equal(configured, join(root, "plans", key));
  assert.equal(await resolveRecordsRoot(root, { env, home: root, explicitRoot: "~/one-run" }), join(root, "one-run"));
  assert.equal(await resolveRecordsRoot(root, { env: { XDG_STATE_HOME: env.XDG_STATE_HOME }, home: root }),
    join(root, "state", "pi", "deep-plan", "records", key));
  for (const state of ["", "relative-state"]) {
    assert.equal(await resolveRecordsRoot(root, { env: { PI_DEEP_PLAN_RECORDS_DIR: "", XDG_STATE_HOME: state }, home: root }),
      join(root, ".local", "state", "pi", "deep-plan", "records", key));
  }
  assert.equal(await resolveRecordsRoot(root, { explicitRoot: "relative-plans", env: {}, home: root }), resolve("relative-plans"));
  await assert.rejects(() => resolveRecordsRoot(root, { explicitRoot: "" }), /must not be empty/);
  assert.deepEqual(await readdir(root), []);
});

test("project keys distinguish same names and follow canonical project paths", async () => {
  const root = await temporaryRoot();
  const first = join(root, "one", "same-name");
  const second = join(root, "two", "same-name");
  await mkdir(first, { recursive: true });
  await mkdir(second, { recursive: true });
  const alias = join(root, "alias");
  await symlink(first, alias, "junction");
  const options = { env: {}, home: root };
  assert.notEqual(await resolveRecordsRoot(first, options), await resolveRecordsRoot(second, options));
  assert.equal(await resolveRecordsRoot(first, options), await resolveRecordsRoot(alias, options));
  const unicode = join(root, "한글");
  await mkdir(unicode);
  assert.match(basename(await resolveRecordsRoot(unicode, options)), /^project-[0-9a-f]{6}$/);
});

test("records-root CLI is read-only and reports the selected parent", async () => {
  const root = await temporaryRoot();
  const script = fileURLToPath(new URL("./records-root.mjs", import.meta.url));
  const env = { ...process.env, PI_DEEP_PLAN_RECORDS_DIR: join(root, "plans") };
  const result = await promisify(execFile)(process.execPath, [script, root], { env });
  assert.equal(result.stdout.trim(), await resolveRecordsRoot(root, { env }));
  assert.equal(result.stderr, "");
  assert.deepEqual(await readdir(root), []);
});
