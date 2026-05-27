import assert from "node:assert/strict";
import test from "node:test";

import { getAvatarFallbackInitial, resolveAvatarUrlCore } from "./avatar-core.mjs";

test("relative upload avatar URLs resolve against the API origin", () => {
  assert.equal(
    resolveAvatarUrlCore("/uploads/avatars/user.png", "https://api.ojikbms.kr"),
    "https://api.ojikbms.kr/uploads/avatars/user.png",
  );
});

test("absolute avatar URLs are left unchanged", () => {
  const discordUrl = "https://cdn.discordapp.com/avatars/1234/hash.png";
  assert.equal(resolveAvatarUrlCore(discordUrl, "https://api.ojikbms.kr"), discordUrl);
});

test("avatar fallback initial is stable for empty or whitespace labels", () => {
  assert.equal(getAvatarFallbackInitial(" Tokakitake "), "T");
  assert.equal(getAvatarFallbackInitial(""), "?");
  assert.equal(getAvatarFallbackInitial("   "), "?");
});
