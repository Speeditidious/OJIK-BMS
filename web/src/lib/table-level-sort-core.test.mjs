import assert from "node:assert/strict";

import { compareByTableLevelsCore, sortTableLevelsCore } from "./table-level-sort-core.mjs";

function level(symbol, slug, value) {
  return { symbol, slug, level: value };
}

function sortLabels(levels) {
  return levels
    .map((entry) => [entry])
    .sort(compareByTableLevelsCore)
    .map(([entry]) => `${entry.symbol}${entry.level}`);
}

assert.deepEqual(
  sortLabels([
    level("sr", "starlight", "10"),
    level("sl", "satellite", "2"),
    level("sl", "satellite", "5"),
    level("st", "stella", "0"),
    level("st", "stella", "8"),
  ]),
  ["st8", "st0", "sl5", "sl2", "sr10"],
);

assert.deepEqual(
  sortLabels([
    level("★", "balgwang", "1"),
    level("▼", "new_balgwang", "5"),
    level("★", "balgwang", "10"),
    level("★★", "overjoy", "1"),
  ]),
  ["★★1", "★10", "★1", "▼5"],
);

assert.deepEqual(
  sortTableLevelsCore([
    level("★", "balgwang", "1"),
    level("▼", "new_balgwang", "5"),
    level("★", "balgwang", "10"),
  ]).map((entry) => `${entry.symbol}${entry.level}`),
  ["★10", "★1", "▼5"],
);

assert.deepEqual(
  sortLabels([
    level("◆", "third", "99"),
    level("★★", "overjoy", "1"),
    level("st", "stella", "0"),
  ]),
  ["st0", "★★1", "◆99"],
);

assert.deepEqual(
  sortLabels([
    level("st", "stella", "12"),
    level("LEVEL ", "5aery", "1"),
    level("★★", "overjoy", "7"),
  ]),
  ["LEVEL 1", "st12", "★★7"],
);

assert.deepEqual(
  sortLabels([
    level("⑦", "7aery", "1"),
    level("⑤", "5aery", "1"),
    level("st", "stella", "12"),
  ]),
  ["⑤1", "⑦1", "st12"],
);
