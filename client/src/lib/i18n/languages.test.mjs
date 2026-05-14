import test from "node:test";
import assert from "node:assert/strict";
import { detectInitialClientLanguage, normalizeLanguage } from "./language-core.js";

test("normalizeLanguage maps supported locale tags", () => {
  assert.equal(normalizeLanguage("ko-KR"), "ko");
  assert.equal(normalizeLanguage("en-US"), "en");
  assert.equal(normalizeLanguage("ja-JP"), "ja");
});

test("detectInitialClientLanguage prefers saved config over navigator language", () => {
  assert.equal(detectInitialClientLanguage("ja", "ko-KR"), "ja");
});

test("detectInitialClientLanguage falls back from navigator then Korean", () => {
  assert.equal(detectInitialClientLanguage(null, "en-US"), "en");
  assert.equal(detectInitialClientLanguage(null, "fr-FR"), "ko");
});
