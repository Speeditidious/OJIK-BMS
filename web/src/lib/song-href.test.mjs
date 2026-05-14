import assert from "node:assert/strict";

const { songHref, parseSongRouteSegment } = await import("./song-href.ts");

const fumenId = "7c5f4de2-0668-4d3f-a59b-4020d9cc4dd2";
const md5 = "a".repeat(32);
const sha256 = "b".repeat(64);

assert.equal(
  songHref({ fumen_id: fumenId, md5, sha256 }),
  `/songs/md5/${md5}`,
  "md5 should be the canonical song detail URL even when fumen_id is available",
);

assert.equal(
  songHref({ md5, sha256 }),
  `/songs/md5/${md5}`,
  "md5 should be preferred when fumen_id is unavailable",
);

assert.equal(
  songHref({ sha256 }),
  `/songs/sha256/${sha256}`,
  "sha256 should be used when md5 is unavailable",
);

assert.equal(
  songHref({ fumen_id: fumenId, sha256 }, "user-1"),
  `/songs/sha256/${sha256}?user_id=user-1`,
  "user_id should be preserved as a query parameter",
);

assert.equal(parseSongRouteSegment(`md5=${md5}`), md5);
assert.equal(parseSongRouteSegment(`sha256=${sha256}`), sha256);
assert.equal(parseSongRouteSegment(`fumen=${fumenId}`), fumenId);
assert.equal(parseSongRouteSegment(`fumen_id=${fumenId}`), fumenId);
