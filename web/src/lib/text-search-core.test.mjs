import test from "node:test";
import assert from "node:assert/strict";

import {
  anyTextMatchesLooseQuery,
  normalizeLooseSearchText,
  textMatchesLooseQuery,
} from "./text-search-core.mjs";

test("normalizeLooseSearchText removes symbols and whitespace", () => {
  assert.equal(normalizeLooseSearchText("[GEN-GAOZO]"), "gengaozo");
  assert.equal(normalizeLooseSearchText(" 질 문 "), "질문");
});

test("textMatchesLooseQuery matches compact queries against symbol-separated text", () => {
  assert.equal(textMatchesLooseQuery("GEN-GAOZO -foon mix-", "gengaozo"), true);
  assert.equal(textMatchesLooseQuery("GEN-GAOZO -foon mix-", "gen gaozo"), true);
});

test("anyTextMatchesLooseQuery searches title and artist candidates", () => {
  assert.equal(anyTextMatchesLooseQuery(["Other", "削除"], "削 除"), true);
  assert.equal(anyTextMatchesLooseQuery(["Other", "削除"], "missing"), false);
});
