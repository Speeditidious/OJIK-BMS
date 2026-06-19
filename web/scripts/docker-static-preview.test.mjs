import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("docker web service serves static export preview on localhost port 3000", async () => {
  const [packageJsonText, composeText] = await Promise.all([
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    readFile(new URL("../../docker-compose.yml", import.meta.url), "utf8"),
  ]);
  const packageJson = JSON.parse(packageJsonText);

  assert.equal(
    packageJson.scripts["preview:static:docker"],
    "npm run build && node scripts/static-preview.mjs --host=0.0.0.0 --port=3000",
  );
  assert.match(composeText, /web:\n(?:  .*\n)*?    command: sh -c "npm run preview:static:docker"/);
  assert.doesNotMatch(composeText, /web:\n(?:  .*\n)*?    command: sh -c "npm run dev"/);
});
