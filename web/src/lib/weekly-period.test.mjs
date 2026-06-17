import assert from "node:assert/strict";
import test from "node:test";

import {
  getWeeklyPeriodForOffset,
  getWeeklyValidOffsetRange,
  getWeeklyWeekNumber,
} from "./weekly-period.mjs";

test("computes the current weekly period from rollover settings and offset", () => {
  const period = getWeeklyPeriodForOffset(
    new Date("2026-06-13T12:00:00.000Z"),
    0,
    { timezone: "Asia/Seoul", day_of_week: "mon", hour: 4, minute: 0 },
  );

  assert.equal(period.periodStart, "2026-06-07T19:00:00.000Z");
  assert.equal(period.periodEnd, "2026-06-14T19:00:00.000Z");
  assert.equal(period.isCurrent, true);
});

test("keeps producing a navigable period for missing historical offsets", () => {
  const period = getWeeklyPeriodForOffset(
    new Date("2026-06-13T12:00:00.000Z"),
    -2,
    { timezone: "Asia/Seoul", day_of_week: "mon", hour: 4, minute: 0 },
  );

  assert.equal(period.periodStart, "2026-05-24T19:00:00.000Z");
  assert.equal(period.periodEnd, "2026-05-31T19:00:00.000Z");
  assert.equal(period.isCurrent, false);
});

const periodsNewestFirst = [
  {
    weekly_id: "weekly-3",
    period_start: "2026-06-21T19:00:00.000Z",
    period_end: "2026-06-28T19:00:00.000Z",
  },
  {
    weekly_id: "weekly-2",
    period_start: "2026-06-14T19:00:00.000Z",
    period_end: "2026-06-21T19:00:00.000Z",
  },
  {
    weekly_id: "weekly-1",
    period_start: "2026-06-07T19:00:00.000Z",
    period_end: "2026-06-14T19:00:00.000Z",
  },
];

test("derives the valid offset range from generated weekly periods", () => {
  const range = getWeeklyValidOffsetRange(
    periodsNewestFirst,
    "2026-06-21T19:00:00.000Z",
  );

  assert.deepEqual(range, { minOffset: -2, maxOffset: 0 });
});

test("returns null offset range when there are no generated weekly periods", () => {
  const range = getWeeklyValidOffsetRange([], "2026-06-21T19:00:00.000Z");

  assert.equal(range, null);
});

test("derives one-based week number from generated weekly periods", () => {
  assert.equal(
    getWeeklyWeekNumber(periodsNewestFirst, "2026-06-07T19:00:00.000Z"),
    1,
  );
  assert.equal(
    getWeeklyWeekNumber(periodsNewestFirst, "2026-06-14T19:00:00.000Z"),
    2,
  );
  assert.equal(
    getWeeklyWeekNumber(periodsNewestFirst, "2026-06-21T19:00:00.000Z"),
    3,
  );
});

test("returns null week number when selected period is not generated", () => {
  assert.equal(
    getWeeklyWeekNumber(periodsNewestFirst, "2026-05-31T19:00:00.000Z"),
    null,
  );
});
