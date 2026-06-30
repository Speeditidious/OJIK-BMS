import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("docker web service serves static export preview on localhost port 3000", async () => {
  const [packageJsonText, composeText, dockerfileText, dockerignoreText] = await Promise.all([
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    readFile(new URL("../../docker-compose.yml", import.meta.url), "utf8"),
    readFile(new URL("../Dockerfile", import.meta.url), "utf8"),
    readFile(new URL("../.dockerignore", import.meta.url), "utf8"),
  ]);
  const packageJson = JSON.parse(packageJsonText);

  assert.equal(
    packageJson.scripts["preview:static:docker"],
    "npm run build && node scripts/static-preview.mjs --host=0.0.0.0 --port=3000",
  );
  assert.match(composeText, /web:\n(?:  .*\n)*?    command: sh -c "npm run preview:static:docker"/);
  assert.doesNotMatch(composeText, /web:\n(?:  .*\n)*?    command: sh -c "npm run dev"/);
  assert.match(composeText, /web:\n(?:  .*\n)*?    user: "\$\{HOST_UID:-1000\}:\$\{HOST_GID:-1000\}"/);
  assert.doesNotMatch(composeText, /web:\n(?:  .*\n)*?      - \/app\/\.next/);
  assert.match(dockerfileText, /FROM nginx:alpine AS runner/);
  assert.match(dockerfileText, /COPY --from=builder \/app\/out \/usr\/share\/nginx\/html/);
  assert.doesNotMatch(dockerfileText, /\.next\/standalone/);
  assert.match(dockerignoreText, /^node_modules\/$/m);
  assert.match(dockerignoreText, /^\.next\/$/m);
  assert.match(dockerignoreText, /^out\/$/m);
});
