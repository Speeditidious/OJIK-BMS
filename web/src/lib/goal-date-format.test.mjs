import test from "node:test";
import assert from "node:assert/strict";

import { formatGoalDate } from "./goal-date-format.mjs";

test("formatGoalDate renders a timezone-aware timestamp as YYYY.MM.DD", () => {
  // Midday UTC — the same calendar day in every timezone the app targets.
  assert.equal(formatGoalDate("2026-08-01T12:00:00+00:00"), "2026.08.01");
});

test("formatGoalDate zero-pads single-digit months and days", () => {
  assert.equal(formatGoalDate("2026-03-09T12:00:00+00:00"), "2026.03.09");
});

test("formatGoalDate returns an empty string for missing values", () => {
  assert.equal(formatGoalDate(null), "");
  assert.equal(formatGoalDate(undefined), "");
  assert.equal(formatGoalDate(""), "");
});

test("formatGoalDate returns an empty string for unparseable input", () => {
  assert.equal(formatGoalDate("not a date"), "");
});
