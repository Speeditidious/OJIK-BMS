import test from "node:test";
import assert from "node:assert/strict";

import { validateGoalTarget } from "./goal-validation-core.mjs";

test("rejects when nothing selected", () => {
  const result = validateGoalTarget({ clear_type: 1, min_bp: 50, rank: "A", rate: 60 }, {});
  assert.equal(result.ok, false);
  assert.deepEqual(result.errors, ["no_metric_selected"]);
});

test("rejects a regression on any selected metric", () => {
  const result = validateGoalTarget(
    { clear_type: 5, min_bp: 10, rank: "AA", rate: 80 },
    { clearType: 4, rate: 90 },
  );
  assert.equal(result.ok, false);
  assert.ok(result.errors.includes("clear_type_worse"));
});

test("rejects an all-equal selection (no improvement)", () => {
  const result = validateGoalTarget(
    { clear_type: 5, min_bp: 10, rank: "AA", rate: 80 },
    { clearType: 5, rate: 80 },
  );
  assert.equal(result.ok, false);
  assert.deepEqual(result.errors, ["no_improvement"]);
});

test("accepts a partial improvement with an unimproved-but-not-regressed metric", () => {
  const result = validateGoalTarget(
    { clear_type: 5, min_bp: 20, rank: "AA", rate: 80 },
    { clearType: 5, minBp: 10 },
  );
  assert.equal(result.ok, true);
  assert.deepEqual(result.improvedMetrics, ["min_bp"]);
});

test("no baseline BP is permissive but not counted as improvement", () => {
  const result = validateGoalTarget(
    { clear_type: 0, min_bp: null, rank: null, rate: null },
    { minBp: 50 },
  );
  assert.equal(result.ok, false);
  assert.deepEqual(result.errors, ["no_improvement"]);
});

test("treats missing baseline clear/rank/rate as the lowest value", () => {
  const result = validateGoalTarget(
    { clear_type: null, min_bp: null, rank: null, rate: null },
    { clearType: 1 },
  );
  assert.equal(result.ok, true);
  assert.deepEqual(result.improvedMetrics, ["clear_type"]);
});
