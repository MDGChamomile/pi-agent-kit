import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, readdir, realpath, rm, symlink, writeFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { basename, join, resolve } from "node:path";
import { afterEach, test } from "node:test";
import { publishPlan } from "./publish-plan.mjs";
import { resolveRecordsRoot } from "./records-root.mjs";

const roots = [];

afterEach(async () => {
  await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })));
});

async function fixture() {
  const root = await mkdtemp(join(tmpdir(), "deep-plan-publish-"));
  roots.push(root);
  return {
    root,
    pending: join(root, "PLAN.pending.md"),
    final: join(root, "PLAN.md"),
  };
}

test("default records are external state and resolution does not create files", async () => {
  const { root } = await fixture();
  const project = await realpath(root);
  const parent = await resolveRecordsRoot(project, { env: {}, home: root });
  assert.equal(parent, join(root, ".local", "state", "pi", "deep-plan", "records", basename(parent)));
  assert.match(basename(parent), new RegExp(`^${basename(project)}-[0-9a-f]{6}$`));
  assert.deepEqual(await readdir(root), []);
});

test("explicit root wins, then persistent override, then absolute XDG state", async () => {
  const { root } = await fixture();
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
  const { root } = await fixture();
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
  const { root } = await fixture();
  const script = fileURLToPath(new URL("./records-root.mjs", import.meta.url));
  const env = { ...process.env, PI_DEEP_PLAN_RECORDS_DIR: join(root, "plans") };
  const result = await promisify(execFile)(process.execPath, [script, root], { env });
  assert.equal(result.stdout.trim(), await resolveRecordsRoot(root, { env }));
  assert.equal(result.stderr, "");
  assert.deepEqual(await readdir(root), []);
});

test("external record publication leaves existing historical records untouched", async () => {
  const { root } = await fixture();
  const historical = join(root, "installed-skill", "records", "old-plan.md");
  await mkdir(join(root, "installed-skill", "records"), { recursive: true });
  await writeFile(historical, "historical plan\n");
  const parent = await resolveRecordsRoot(root, { env: {}, home: root });
  const record = join(parent, "20260927-example");
  await mkdir(record, { recursive: true });
  const pending = join(record, "PLAN.pending.md");
  const final = join(record, "PLAN.md");
  await writeFile(pending, "verified plan\n");
  await publishPlan(pending, final);
  assert.equal(await readFile(final, "utf8"), "verified plan\n");
  assert.equal(await readFile(historical, "utf8"), "historical plan\n");
  await assert.rejects(() => mkdir(record), { code: "EEXIST" });
});

test("publishes a verified pending plan without leaving the pending name", async () => {
  const paths = await fixture();
  await writeFile(paths.pending, "verified plan\n");

  const result = await publishPlan(paths.pending, paths.final);

  assert.equal(result.cleanupWarning, undefined);
  assert.equal(await readFile(paths.final, "utf8"), "verified plan\n");
  await assert.rejects(() => readFile(paths.pending), { code: "ENOENT" });
});

test("never replaces an existing PLAN.md", async () => {
  const paths = await fixture();
  await writeFile(paths.pending, "new plan\n");
  await writeFile(paths.final, "existing plan\n");

  await assert.rejects(() => publishPlan(paths.pending, paths.final), /already exists; existing content was preserved/);

  assert.equal(await readFile(paths.final, "utf8"), "existing plan\n");
  assert.equal(await readFile(paths.pending, "utf8"), "new plan\n");
});

test("a pending-name cleanup failure cannot invalidate the published PLAN.md", async () => {
  const paths = await fixture();
  await writeFile(paths.pending, "verified plan\n");

  const result = await publishPlan(paths.pending, paths.final, {
    removePending: async () => {
      throw new Error("simulated cleanup failure");
    },
  });

  assert.match(result.cleanupWarning, /simulated cleanup failure/);
  assert.equal(await readFile(paths.final, "utf8"), "verified plan\n");
  assert.equal(await readFile(paths.pending, "utf8"), "verified plan\n");
});

test("a hard-link failure leaves PLAN absent and the pending file untouched", async () => {
  const paths = await fixture();
  await writeFile(paths.pending, "verified plan\n");

  await assert.rejects(
    () => publishPlan(paths.pending, paths.final, {
      createFinal: async () => {
        const error = new Error("simulated unsupported filesystem");
        error.code = "EPERM";
        throw error;
      },
    }),
    /atomic no-clobber PLAN publication failed: simulated unsupported filesystem/,
  );

  await assert.rejects(() => readFile(paths.final), { code: "ENOENT" });
  assert.equal(await readFile(paths.pending, "utf8"), "verified plan\n");
});

test("rejects publication across directories before creating PLAN.md", async () => {
  const first = await fixture();
  const second = await fixture();
  await writeFile(first.pending, "verified plan\n");

  await assert.rejects(() => publishPlan(first.pending, second.final), /same record directory/);
  await assert.rejects(() => readFile(second.final), { code: "ENOENT" });
});
