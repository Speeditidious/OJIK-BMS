import assert from "node:assert/strict";
import test from "node:test";

import { getWeeklyPeriodForOffset } from "./weekly-period.mjs";

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
