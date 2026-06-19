import test from "node:test";
import assert from "node:assert/strict";
import {
  detectLanguageFromRequestParts,
  detectNavigatorLanguage,
  normalizeLanguage,
  parseAcceptLanguage,
} from "./language-core.mjs";

test("normalizeLanguage maps supported locale tags to app languages", () => {
  assert.equal(normalizeLanguage("ko-KR"), "ko");
  assert.equal(normalizeLanguage("en-US"), "en");
  assert.equal(normalizeLanguage("ja-JP"), "ja");
});

test("parseAcceptLanguage respects q-values and supported languages", () => {
  assert.equal(parseAcceptLanguage("fr-FR,ja;q=0.7,en-US;q=0.9,ko;q=0.3"), "en");
});

test("detectLanguageFromRequestParts prioritizes manual saved language", () => {
  assert.equal(
    detectLanguageFromRequestParts({
      manualCookie: "ja",
      autoCookie: "en",
      acceptLanguage: "ko-KR,ko;q=0.9",
      country: "KR",
    }),
    "ja",
  );
});

test("detectLanguageFromRequestParts falls through to region then Korean fallback", () => {
  assert.equal(detectLanguageFromRequestParts({ country: "JP" }), "ja");
  assert.equal(detectLanguageFromRequestParts({ country: "US" }), "en");
  assert.equal(detectLanguageFromRequestParts({ country: "FR" }), "en");
  assert.equal(detectLanguageFromRequestParts({}), "ko");
});

test("detectNavigatorLanguage uses the first supported browser language", () => {
  assert.equal(detectNavigatorLanguage(["fr-FR", "ja-JP", "en-US"]), "ja");
  assert.equal(detectNavigatorLanguage(["en-US", "ko-KR"]), "en");
  assert.equal(detectNavigatorLanguage(["fr-FR", "de-DE"]), null);
});
