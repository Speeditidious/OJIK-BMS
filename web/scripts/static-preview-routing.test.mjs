import assert from "node:assert/strict";
import test from "node:test";

import {
  createRedirectMatcher,
  getStaticFileCandidates,
  parseRedirects,
} from "./static-preview-routing.mjs";

const redirectsText = `
/dashboard/day/:date /dashboard/day/__static__/ 200
/issues/new /issues/new/index.html 200
/issues/:issueId /issues/__static__/ 200
/songs/md5/:hash /songs/md5/__static__/ 200
/songs/sha256/:hash /songs/sha256/__static__/ 200
/u/:username /u/__static__/ 200
/users/:userId/dashboard /users/__static__/dashboard/ 200
/users/:userId /users/__static__/ 200
/* /index.html 200
`;

test("matches Cloudflare Pages dynamic route rewrites in declaration order", () => {
  const matcher = createRedirectMatcher(parseRedirects(redirectsText));

  assert.equal(matcher("/users/123/dashboard"), "/users/__static__/dashboard/");
  assert.equal(matcher("/users/123/dashboard/"), "/users/__static__/dashboard/");
  assert.equal(matcher("/users/123"), "/users/__static__/");
  assert.equal(matcher("/issues/new"), "/issues/new/index.html");
  assert.equal(matcher("/issues/42"), "/issues/__static__/");
  assert.equal(matcher("/songs/sha256/abc"), "/songs/sha256/__static__/");
});

test("falls back to the exported index page when no specific rule matches", () => {
  const matcher = createRedirectMatcher(parseRedirects(redirectsText));

  assert.equal(matcher("/unknown/deep/link"), "/index.html");
});

test("ignores unsupported redirect statuses for static preview routing", () => {
  const matcher = createRedirectMatcher(
    parseRedirects(`
/old /new 301
/users/:userId/dashboard /users/__static__/dashboard/ 200
`),
  );

  assert.equal(matcher("/old"), null);
  assert.equal(matcher("/users/abc/dashboard"), "/users/__static__/dashboard/");
});

test("builds exported file candidates for clean static paths", () => {
  assert.deepEqual(getStaticFileCandidates("/users/__static__/dashboard/"), [
    "users/__static__/dashboard/index.html",
  ]);
  assert.deepEqual(getStaticFileCandidates("/index.html"), ["index.html"]);
  assert.deepEqual(getStaticFileCandidates("/favicon.ico"), ["favicon.ico"]);
  assert.deepEqual(getStaticFileCandidates("/tables"), ["tables", "tables.html", "tables/index.html"]);
});

test("rejects unsafe static file paths", () => {
  assert.deepEqual(getStaticFileCandidates("/../package.json"), []);
  assert.deepEqual(getStaticFileCandidates("/%2e%2e/package.json"), []);
});
