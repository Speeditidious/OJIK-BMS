import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import nextConfig from "../../next.config.mjs";

test("static export config leaves routing to Cloudflare Pages and static preview", () => {
  assert.equal(nextConfig.output, "export");
  assert.equal("rewrites" in nextConfig, false);
});

test("static export build cleans out before next build", async () => {
  const packageJsonText = await readFile(new URL("../../package.json", import.meta.url), "utf8");
  const packageJson = JSON.parse(packageJsonText);

  assert.equal(packageJson.scripts["clean:export"], "node scripts/clean-export.mjs");
  assert.equal(packageJson.scripts.prebuild, "npm run clean:export");
});

test("root layout uses local Inter instead of Google font fetches", async () => {
  const layoutSource = await readFile(new URL("../app/layout.tsx", import.meta.url), "utf8");

  assert.match(layoutSource, /next\/font\/local/);
  assert.doesNotMatch(layoutSource, /next\/font\/google/);
});
