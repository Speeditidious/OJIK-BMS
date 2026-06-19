import assert from "node:assert/strict";
import test from "node:test";

import nextConfig from "../../next.config.mjs";

test("static export config leaves routing to Cloudflare Pages and static preview", () => {
  assert.equal(nextConfig.output, "export");
  assert.equal("rewrites" in nextConfig, false);
});
