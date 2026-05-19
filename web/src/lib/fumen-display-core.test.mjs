import test from "node:test";
import assert from "node:assert/strict";
import { decodeFumenDisplayText } from "./fumen-display-core.mjs";

test("decodeFumenDisplayText decodes quoted fumen titles from table data", () => {
  assert.equal(decodeFumenDisplayText("Alice &quot;Another&quot;"), 'Alice "Another"');
});

test("decodeFumenDisplayText preserves non-entity BMS text", () => {
  assert.equal(decodeFumenDisplayText("★1 星の器 / ZUN"), "★1 星の器 / ZUN");
});

test("decodeFumenDisplayText preserves invalid numeric entities", () => {
  assert.equal(decodeFumenDisplayText("bad &#999999999999; title"), "bad &#999999999999; title");
});
