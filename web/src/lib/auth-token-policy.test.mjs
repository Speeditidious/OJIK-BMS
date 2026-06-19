import assert from "node:assert/strict";
import test from "node:test";

import { getRefreshFailureKind, shouldClearTokensForFetchUserError } from "./auth-token-policy.mjs";

test("only definitive refresh auth failures invalidate stored tokens", () => {
  assert.equal(getRefreshFailureKind(401), "invalid");
  assert.equal(getRefreshFailureKind(403), "invalid");
  assert.equal(getRefreshFailureKind(500), "unavailable");
  assert.equal(getRefreshFailureKind(0), "unavailable");
});

test("fetchUser keeps tokens for transient API failures", () => {
  assert.equal(shouldClearTokensForFetchUserError(new Error("Authentication required")), true);
  assert.equal(shouldClearTokensForFetchUserError(new Error("Failed to fetch")), false);
  assert.equal(shouldClearTokensForFetchUserError(new Error("API error: 500")), false);
});
