import test from "node:test";
import assert from "node:assert/strict";

import {
  buildMonthCells,
  getMonthRange,
  isMonthAfter,
  pad2,
  previewRange,
  shiftMonth,
  toDateString,
} from "./calendar-grid-core.mjs";

test("pad2 and toDateString produce sortable ISO dates", () => {
  assert.equal(pad2(3), "03");
  assert.equal(pad2(12), "12");
  assert.equal(toDateString(2026, 8, 3), "2026-08-03");
});

test("shiftMonth wraps across year boundaries", () => {
  assert.deepEqual(shiftMonth(2026, 1, -1), { year: 2025, month: 12 });
  assert.deepEqual(shiftMonth(2026, 12, 1), { year: 2027, month: 1 });
  assert.deepEqual(shiftMonth(2026, 8, 1), { year: 2026, month: 9 });
});

test("buildMonthCells always returns six full weeks", () => {
  for (const [year, month] of [[2026, 2], [2026, 8], [2024, 2]]) {
    assert.equal(buildMonthCells(year, month).length, 42, `${year}-${month}`);
  }
});

test("buildMonthCells pads with adjacent months and flags the current one", () => {
  // 2026-08-01 is a Saturday, so the grid opens with six trailing July days.
  const cells = buildMonthCells(2026, 8);
  assert.equal(cells[0].dateStr, "2026-07-26");
  assert.equal(cells[0].currentMonth, false);
  assert.equal(cells[6].dateStr, "2026-08-01");
  assert.equal(cells[6].currentMonth, true);

  const currentMonthDays = cells.filter((cell) => cell.currentMonth);
  assert.equal(currentMonthDays.length, 31);
  assert.equal(currentMonthDays.at(-1).dateStr, "2026-08-31");
});

test("buildMonthCells handles a leap February", () => {
  const cells = buildMonthCells(2024, 2).filter((cell) => cell.currentMonth);
  assert.equal(cells.length, 29);
  assert.equal(cells.at(-1).dateStr, "2024-02-29");
});

test("getMonthRange spans the whole month", () => {
  assert.deepEqual(getMonthRange(2026, 2), { from: "2026-02-01", to: "2026-02-28" });
  assert.deepEqual(getMonthRange(2024, 2), { from: "2024-02-01", to: "2024-02-29" });
  assert.deepEqual(getMonthRange(2026, 8), { from: "2026-08-01", to: "2026-08-31" });
});

test("isMonthAfter compares a month's first day against a reference date", () => {
  assert.equal(isMonthAfter(2026, 9, "2026-08-03"), true);
  assert.equal(isMonthAfter(2026, 8, "2026-08-03"), false);
  assert.equal(isMonthAfter(2026, 7, "2026-08-03"), false);
});

test("previewRange only previews while exactly one bound is set", () => {
  assert.equal(previewRange(null, null, "2026-07-10"), null);
  assert.equal(previewRange("2026-07-01", "2026-07-20", "2026-07-10"), null);
  assert.equal(previewRange("2026-07-01", null, null), null);
});

test("previewRange extends forward from the start date", () => {
  assert.deepEqual(previewRange("2026-07-01", null, "2026-07-10"), {
    from: "2026-07-01",
    to: "2026-07-10",
  });
});

test("previewRange flips when hovering before the start date", () => {
  assert.deepEqual(previewRange("2026-07-10", null, "2026-07-01"), {
    from: "2026-07-01",
    to: "2026-07-10",
  });
});

test("previewRange collapses to a single day when hovering the start date", () => {
  assert.deepEqual(previewRange("2026-07-10", null, "2026-07-10"), {
    from: "2026-07-10",
    to: "2026-07-10",
  });
});
