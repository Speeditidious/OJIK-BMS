import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import { cleanExportDirectory } from "./clean-export.mjs";

test("removes the static export directory before build", async () => {
  const calls = [];

  const result = await cleanExportDirectory("/repo/web/out", {
    remove: async (target, options) => calls.push({ target, options }),
    warn: () => {},
  });

  assert.deepEqual(calls, [{ target: "/repo/web/out", options: { recursive: true, force: true } }]);
  assert.deepEqual(result, { action: "removed", path: "/repo/web/out" });
});

test("moves permission-blocked export directories aside so build can recreate out", async () => {
  const moves = [];

  const result = await cleanExportDirectory("/repo/web/out", {
    remove: async () => {
      const error = new Error("permission denied");
      error.code = "EACCES";
      throw error;
    },
    move: async (from, to) => moves.push({ from, to }),
    now: () => new Date("2026-06-29T04:05:06.789Z"),
    warn: () => {},
  });

  assert.equal(moves.length, 1);
  assert.equal(moves[0].from, "/repo/web/out");
  assert.match(moves[0].to, /\/repo\/web\/\.out-stale-2026-06-29T040506789Z-\d+$/);
  assert.deepEqual(result, { action: "moved", path: moves[0].to });
});

test("keeps non-permission cleanup failures visible", async () => {
  const error = new Error("disk problem");
  error.code = "EIO";

  await assert.rejects(
    () =>
      cleanExportDirectory(path.join("/repo", "web", "out"), {
        remove: async () => {
          throw error;
        },
        warn: () => {},
      }),
    error,
  );
});
