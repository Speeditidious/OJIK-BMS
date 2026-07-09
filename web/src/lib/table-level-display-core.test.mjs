import test from "node:test";
import assert from "node:assert/strict";
import {
  formatTableLevelForDisplay,
  formatTableLevelWithSymbolForDisplay,
} from "./table-level-display-core.mjs";

test("formatTableLevelForDisplay strips numeric AERY LEVEL prefix for display only", () => {
  assert.equal(formatTableLevelForDisplay({ tableSlug: "5aery", level: "LEVEL 19+" }), "19+");
  assert.equal(formatTableLevelForDisplay({ tableSlug: "7aery", level: "LEVEL 19+" }), "19+");
  assert.equal(formatTableLevelForDisplay({ tableName: "5KEYS AERY", level: "LEVEL 1" }), "1");
  assert.equal(formatTableLevelForDisplay({ tableName: "7KEYS AERY", level: "LEVEL 1" }), "1");
});

test("formatTableLevelForDisplay strips AERY LEVEL prefix for display only", () => {
  assert.equal(formatTableLevelForDisplay({ tableSlug: "5aery", level: "LEVEL SPECIAL" }), "SPECIAL");
  assert.equal(formatTableLevelWithSymbolForDisplay({ tableSymbol: "⑤", level: "LEVEL SPECIAL" }), "⑤SPECIAL");
  assert.equal(formatTableLevelWithSymbolForDisplay({ tableSymbol: "⑦", level: "LEVEL SPECIAL" }), "⑦SPECIAL");
});

test("formatTableLevelForDisplay preserves non-AERY table levels", () => {
  assert.equal(formatTableLevelForDisplay({ tableSlug: "satellite", level: "LEVEL 19+" }), "LEVEL 19+");
  assert.equal(formatTableLevelForDisplay({ tableName: "Other", level: "sl12" }), "sl12");
});
