import test from "node:test";
import assert from "node:assert/strict";

import {
  activeFilterCount,
  applyLevelDisplayPreference,
  emptyAxisFilter,
  emptyGoalFilter,
  filterGoals,
  goalFacetCounts,
  goalFilterOptions,
  isGoalFilterActive,
  isTableEnabled,
  levelKey,
  matchesAxisFilter,
  setExcluded,
  splitGoalsByAxis,
  toggleExcluded,
} from "./goal-filter-core.mjs";

const TABLES = [
  {
    slug: "insane",
    name: "Insane",
    symbol: "★",
    level_order: ["12", "11"],
    preference_visible: true,
    preference_level_order: ["12"],
  },
  {
    slug: "normal",
    name: "Normal",
    symbol: "☆",
    level_order: ["9"],
    preference_visible: false,
    preference_level_order: [],
  },
  {
    slug: "dan",
    name: "Dan",
    symbol: "段",
    level_order: [],
    preference_visible: true,
    preference_level_order: [],
  },
];

function chartGoal(overrides = {}) {
  return {
    goal_id: "c",
    goal_type: "chart",
    target_clear_type: null,
    target_min_bp: null,
    target_rank: null,
    target_rate: null,
    created_at: "2026-07-01T10:00:00+00:00",
    achieved_recorded_at: null,
    table_levels: [],
    course_table_slug: null,
    ...overrides,
  };
}

function courseGoal(overrides = {}) {
  return { ...chartGoal(), goal_id: "k", goal_type: "course", ...overrides };
}

const insane12 = { slug: "insane", symbol: "★", level: "12" };
const insane11 = { slug: "insane", symbol: "★", level: "11" };
const normal9 = { slug: "normal", symbol: "☆", level: "9" };

// ── defaults ────────────────────────────────────────────────────────────────

test("an empty filter matches everything and reports itself inactive", () => {
  const filter = emptyGoalFilter();
  const options = goalFilterOptions([chartGoal({ target_clear_type: 7 })], TABLES);
  assert.equal(isGoalFilterActive(filter, options), false);
  assert.equal(activeFilterCount(filter, options), 0);
  assert.equal(matchesAxisFilter(chartGoal(), filter.chart, "chart"), true);
});

// ── options ─────────────────────────────────────────────────────────────────

test("chart options follow the server table order and each table's level order", () => {
  const goals = [
    chartGoal({ goal_id: "a", table_levels: [normal9] }),
    chartGoal({ goal_id: "b", table_levels: [insane11, insane12] }),
  ];
  const { chart } = goalFilterOptions(goals, TABLES);

  assert.deepEqual(
    chart.tables.map((t) => [t.slug, t.levels.map((l) => l.level)]),
    [["insane", ["12", "11"]], ["normal", ["9"]]],
  );
});

test("a level missing from the server order is appended, not dropped", () => {
  const goals = [chartGoal({ table_levels: [{ slug: "insane", symbol: "★", level: "0" }, insane12] })];
  const { chart } = goalFilterOptions(goals, TABLES);
  assert.deepEqual(chart.tables[0].levels.map((l) => l.level), ["12", "0"]);
});

test("options are computed per axis and never leak across", () => {
  const goals = [
    chartGoal({ target_clear_type: 7, target_rank: "AAA", table_levels: [insane12] }),
    courseGoal({ target_clear_type: 4, course_table_slug: "dan" }),
  ];
  const { chart, course } = goalFilterOptions(goals, TABLES);

  assert.deepEqual(chart.clearTypes, [7]);
  assert.deepEqual(chart.ranks, ["AAA"]);
  assert.deepEqual(course.clearTypes, [4]);
  assert.deepEqual(course.ranks, []);
  assert.deepEqual(course.tables.map((t) => t.slug), ["dan"]);
  assert.deepEqual(course.tables[0].levels, []);
  assert.deepEqual(chart.tables.map((t) => t.slug), ["insane"]);
});

test("clear types sort high to low and ranks follow RANK_SORT_ORDER", () => {
  const goals = [
    chartGoal({ goal_id: "a", target_clear_type: 3, target_rank: "AA" }),
    chartGoal({ goal_id: "b", target_clear_type: 7, target_rank: "MAX-" }),
    chartGoal({ goal_id: "c", target_clear_type: 5, target_rank: "AAA" }),
  ];
  const { chart } = goalFilterOptions(goals, TABLES);
  assert.deepEqual(chart.clearTypes, [7, 5, 3]);
  assert.deepEqual(chart.ranks, ["MAX-", "AAA", "AA"]);
});

test("options report empty categories so the UI can explain the gap", () => {
  const { chart, course } = goalFilterOptions([chartGoal()], TABLES);
  assert.deepEqual(chart.ranks, []);
  assert.deepEqual(chart.tables, []);
  assert.equal(chart.hasRate, false);
  assert.equal(chart.hasBp, false);
  assert.deepEqual(course.tables, []);
});

test("hasRate and hasBp track whether any goal carries the metric", () => {
  const { chart } = goalFilterOptions(
    [chartGoal({ target_rate: 90 }), chartGoal({ goal_id: "b", target_min_bp: 3 })],
    TABLES,
  );
  assert.equal(chart.hasRate, true);
  assert.equal(chart.hasBp, true);
});

// ── chip toggle semantics ───────────────────────────────────────────────────

test("a clear goal hides when its clear chip is disabled and it has no lit rank chip", () => {
  const filter = { ...emptyAxisFilter(), excludedClearTypes: [7] };
  assert.equal(matchesAxisFilter(chartGoal({ target_clear_type: 7 }), filter, "chart"), false);
  assert.equal(matchesAxisFilter(chartGoal({ target_clear_type: 5 }), filter, "chart"), true);
});

test("disabling AAA does not hide a HARD AAA goal while HARD is still lit", () => {
  const filter = { ...emptyAxisFilter(), excludedRanks: ["AAA"] };
  assert.equal(
    matchesAxisFilter(chartGoal({ target_clear_type: 5, target_rank: "AAA" }), filter, "chart"),
    true,
  );
});

test("a HARD AAA goal hides only when both HARD and AAA are disabled", () => {
  const filter = { ...emptyAxisFilter(), excludedClearTypes: [5], excludedRanks: ["AAA"] };
  assert.equal(
    matchesAxisFilter(chartGoal({ target_clear_type: 5, target_rank: "AAA" }), filter, "chart"),
    false,
  );
});

test("a goal without a value in a disabled chip category stays visible", () => {
  const filter = { ...emptyAxisFilter(), excludedClearTypes: [7], excludedRanks: ["AAA"] };
  assert.equal(matchesAxisFilter(chartGoal({ target_min_bp: 4 }), filter, "chart"), true);
});

test("a chart goal survives while any of its table levels is still enabled", () => {
  const filter = { ...emptyAxisFilter(), excludedLevels: [levelKey("insane", "12")] };
  assert.equal(
    matchesAxisFilter(chartGoal({ table_levels: [insane12, normal9] }), filter, "chart"), true,
  );
  assert.equal(matchesAxisFilter(chartGoal({ table_levels: [insane12] }), filter, "chart"), false);
  assert.equal(matchesAxisFilter(chartGoal({ table_levels: [] }), filter, "chart"), true);
});

test("a chart goal hides when all of its table levels are disabled", () => {
  const filter = {
    ...emptyAxisFilter(),
    excludedLevels: [levelKey("insane", "12"), levelKey("normal", "9")],
  };
  assert.equal(
    matchesAxisFilter(chartGoal({ table_levels: [insane12, normal9] }), filter, "chart"),
    false,
  );
});

test("the course axis filters on the course's source table", () => {
  const filter = { ...emptyAxisFilter(), excludedTables: ["dan"] };
  assert.equal(
    matchesAxisFilter(courseGoal({ course_table_slug: "dan" }), filter, "course"), false,
  );
  assert.equal(
    matchesAxisFilter(courseGoal({ course_table_slug: "other" }), filter, "course"), true,
  );
  assert.equal(matchesAxisFilter(courseGoal({ course_table_slug: null }), filter, "course"), true);
});

test("rate and bp ranges only apply to goals that target the metric", () => {
  const rateFilter = { ...emptyAxisFilter(), rateMin: 80, rateMax: 90 };
  assert.equal(matchesAxisFilter(chartGoal({ target_rate: 80 }), rateFilter, "chart"), true);
  assert.equal(matchesAxisFilter(chartGoal({ target_rate: 90 }), rateFilter, "chart"), true);
  assert.equal(matchesAxisFilter(chartGoal({ target_rate: 79.9 }), rateFilter, "chart"), false);
  assert.equal(matchesAxisFilter(chartGoal({ target_rate: null }), rateFilter, "chart"), true);

  const bpFilter = { ...emptyAxisFilter(), bpMax: 10 };
  assert.equal(matchesAxisFilter(chartGoal({ target_min_bp: 0 }), bpFilter, "chart"), true);
  assert.equal(matchesAxisFilter(chartGoal({ target_min_bp: 11 }), bpFilter, "chart"), false);
  assert.equal(matchesAxisFilter(chartGoal({ target_min_bp: null }), bpFilter, "chart"), true);
});

test("rate and bp ranges are hard filters regardless of lit chip matches", () => {
  const rateFilter = { ...emptyAxisFilter(), rateMin: 80, rateMax: 90 };
  assert.equal(
    matchesAxisFilter(
      chartGoal({ target_clear_type: 5, target_rank: "AAA", target_rate: 79 }),
      rateFilter,
      "chart",
    ),
    false,
  );

  const bpFilter = { ...emptyAxisFilter(), bpMax: 10 };
  assert.equal(
    matchesAxisFilter(
      chartGoal({ target_clear_type: 5, target_rank: "AAA", target_min_bp: 11 }),
      bpFilter,
      "chart",
    ),
    false,
  );
});

test("date ranges always narrow the lit-chip union", () => {
  const filter = {
    ...emptyAxisFilter(), excludedClearTypes: [5], createdFrom: "2026-07-01", createdTo: "2026-07-31",
  };
  assert.equal(
    matchesAxisFilter(
      chartGoal({ target_clear_type: 7, created_at: "2026-06-30T23:00:00+00:00" }), filter, "chart",
    ),
    false,
  );
  assert.equal(
    matchesAxisFilter(
      chartGoal({ target_clear_type: 7, created_at: "2026-07-31T23:00:00+00:00" }), filter, "chart",
    ),
    true,
  );
});

test("achieved range filters on achieved_recorded_at", () => {
  const filter = { ...emptyAxisFilter(), achievedFrom: "2026-07-10", achievedTo: "2026-07-10" };
  assert.equal(
    matchesAxisFilter(chartGoal({ achieved_recorded_at: "2026-07-10T02:00:00+00:00" }), filter, "chart"),
    true,
  );
  assert.equal(
    matchesAxisFilter(chartGoal({ achieved_recorded_at: "2026-07-11T02:00:00+00:00" }), filter, "chart"),
    false,
  );
  assert.equal(
    matchesAxisFilter(chartGoal({ achieved_recorded_at: null }), filter, "chart"), false,
  );
});

// ── axis split ──────────────────────────────────────────────────────────────

test("splitGoalsByAxis separates chart and course goals", () => {
  const goals = [chartGoal(), courseGoal(), chartGoal({ goal_id: "c2" })];
  const { chart, course } = splitGoalsByAxis(goals);
  assert.deepEqual(chart.map((g) => g.goal_id), ["c", "c2"]);
  assert.deepEqual(course.map((g) => g.goal_id), ["k"]);
});

test("filterGoals applies each axis to its own goals and keeps input order", () => {
  const goals = [
    chartGoal({ goal_id: "a", target_clear_type: 7 }),
    courseGoal({ goal_id: "b", target_clear_type: 7 }),
    chartGoal({ goal_id: "c", target_clear_type: 5 }),
  ];
  const filter = {
    chart: { ...emptyAxisFilter(), excludedClearTypes: [7] },
    course: emptyAxisFilter(),
  };
  assert.deepEqual(filterGoals(goals, filter).map((g) => g.goal_id), ["b", "c"]);
});

test("turning off an axis hides every goal on that axis", () => {
  const goals = [
    chartGoal({ goal_id: "a" }),
    courseGoal({ goal_id: "b" }),
    chartGoal({ goal_id: "c" }),
  ];
  const filter = {
    chart: { ...emptyAxisFilter(), visible: false },
    course: emptyAxisFilter(),
  };
  assert.deepEqual(filterGoals(goals, filter).map((g) => g.goal_id), ["b"]);
});

// ── level-display preferences ──────────────────────────────────────────────

test("level-display preferences trim chart table levels and hide fully-hidden charts", () => {
  const goals = [
    chartGoal({ goal_id: "a", table_levels: [insane12, insane11, normal9] }),
    chartGoal({ goal_id: "b", table_levels: [normal9] }),
  ];
  const filtered = applyLevelDisplayPreference(goals, TABLES, true);

  assert.deepEqual(filtered.map((g) => g.goal_id), ["a"]);
  assert.deepEqual(filtered[0].table_levels, [insane12]);
});

test("level-display preferences hide courses whose source table is hidden", () => {
  const goals = [
    courseGoal({ goal_id: "a", course_table_slug: "dan" }),
    courseGoal({ goal_id: "b", course_table_slug: "normal" }),
    courseGoal({ goal_id: "c", course_table_slug: "unknown" }),
  ];
  assert.deepEqual(
    applyLevelDisplayPreference(goals, TABLES, true).map((g) => g.goal_id),
    ["a", "c"],
  );
  assert.deepEqual(applyLevelDisplayPreference(goals, TABLES, false), goals);
});

// ── table <-> level linkage ─────────────────────────────────────────────────

test("a table is enabled while any of its levels is enabled", () => {
  const keys = [levelKey("insane", "12"), levelKey("insane", "11")];
  assert.equal(isTableEnabled(keys, emptyAxisFilter()), true);
  assert.equal(
    isTableEnabled(keys, { ...emptyAxisFilter(), excludedLevels: [keys[0]] }), true,
  );
  assert.equal(isTableEnabled(keys, { ...emptyAxisFilter(), excludedLevels: keys }), false);
});

test("setExcluded turns a whole table off and back on", () => {
  const keys = [levelKey("insane", "12"), levelKey("insane", "11")];
  const off = setExcluded([], keys, true);
  assert.deepEqual(off.slice().sort(), keys.slice().sort());
  assert.deepEqual(setExcluded(off, keys, false), []);
});

test("setExcluded does not duplicate already-excluded values", () => {
  const keys = [levelKey("insane", "12")];
  assert.deepEqual(setExcluded(keys, keys, true), keys);
});

test("toggleExcluded adds and removes a single value", () => {
  assert.deepEqual(toggleExcluded([], "x"), ["x"]);
  assert.deepEqual(toggleExcluded(["x"], "x"), []);
});

// ── facet counts ────────────────────────────────────────────────────────────

test("facet counts ignore disabled chips within their own category", () => {
  const goals = [
    chartGoal({ goal_id: "a", target_clear_type: 7, target_rank: "AAA" }),
    chartGoal({ goal_id: "b", target_clear_type: 5, target_rank: "AAA" }),
    chartGoal({ goal_id: "c", target_clear_type: 5, target_rank: "AA" }),
  ];
  const options = goalFilterOptions(goals, TABLES);
  const filter = {
    chart: { ...emptyAxisFilter(), excludedClearTypes: [5], excludedRanks: ["AA"] },
    course: emptyAxisFilter(),
  };
  const counts = goalFacetCounts(goals, filter, options);

  // Rank AA is disabled, but goal "c" still has CLEAR 5 lit when counting clear chips.
  assert.deepEqual(counts.chart.clearTypes, { 5: 2, 7: 1 });
  // Clear 5 is disabled, but goals "b" and "c" still feed rank chips by their rank.
  assert.deepEqual(counts.chart.ranks, { AAA: 2, AA: 1 });
});

test("table counts aggregate the table's levels", () => {
  const goals = [
    chartGoal({ goal_id: "a", table_levels: [insane12] }),
    chartGoal({ goal_id: "b", table_levels: [insane11] }),
    chartGoal({ goal_id: "c", table_levels: [normal9] }),
  ];
  const options = goalFilterOptions(goals, TABLES);
  const counts = goalFacetCounts(goals, emptyGoalFilter(), options);

  assert.deepEqual(counts.chart.levels, {
    [levelKey("insane", "12")]: 1,
    [levelKey("insane", "11")]: 1,
    [levelKey("normal", "9")]: 1,
  });
  assert.deepEqual(counts.chart.tables, { insane: 2, normal: 1 });
});

// ── active count ────────────────────────────────────────────────────────────

test("activeFilterCount counts every narrowed dimension across both axes", () => {
  const goals = [
    chartGoal({ target_clear_type: 7, target_rate: 90, table_levels: [insane12] }),
    courseGoal({ target_clear_type: 4, course_table_slug: "dan" }),
  ];
  const options = goalFilterOptions(goals, TABLES);
  const filter = {
    chart: {
      ...emptyAxisFilter(),
      excludedClearTypes: [7],
      rateMin: 80,
      createdFrom: "2026-07-01",
    },
    course: { ...emptyAxisFilter(), excludedTables: ["dan"] },
  };
  assert.equal(activeFilterCount(filter, options), 4);
  assert.equal(isGoalFilterActive(filter, options), true);
});

test("exclusions for values no longer present do not count as active", () => {
  const goals = [chartGoal({ target_clear_type: 7 })];
  const options = goalFilterOptions(goals, TABLES);
  // CLEAR 3 was excluded while such a goal existed; the goal is gone now.
  const filter = { chart: { ...emptyAxisFilter(), excludedClearTypes: [3] }, course: emptyAxisFilter() };
  assert.equal(activeFilterCount(filter, options), 0);
  assert.equal(isGoalFilterActive(filter, options), false);
});

test("turning off level-display preference filtering counts as an active change", () => {
  const options = goalFilterOptions([chartGoal()], TABLES);
  const filter = { ...emptyGoalFilter(), applyLevelDisplayPrefs: false };
  assert.equal(activeFilterCount(filter, options), 1);
  assert.equal(isGoalFilterActive(filter, options), true);
});

test("turning off an axis counts as an active change", () => {
  const options = goalFilterOptions([chartGoal()], TABLES);
  const filter = { chart: { ...emptyAxisFilter(), visible: false }, course: emptyAxisFilter() };
  assert.equal(activeFilterCount(filter, options), 1);
  assert.equal(isGoalFilterActive(filter, options), true);
});
