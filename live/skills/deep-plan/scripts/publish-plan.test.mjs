import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, test } from "node:test";
import { publishPlan } from "./publish-plan.mjs";

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
