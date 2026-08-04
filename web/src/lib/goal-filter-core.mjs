// Pure goal-filter logic shared by GoalsPanel / GoalFilterBar / GoalFilterAxis.
// No React or DOM access — everything here is unit-tested with node:test.
//
// Chip toggles are stored as disabled values: an empty list means every chip is
// lit. Disabled chips are ignored, not treated as negative predicates. A goal is
// shown when any still-lit chip/range matches it; date ranges remain hard
// scoping filters.

import { RANK_SORT_ORDER } from "./score-rank-display-core.mjs";

const LEVEL_KEY_SEPARATOR = ":";

/** Stable identity for a (difficulty table, level) pair, used as a chip key. */
export function levelKey(slug, level) {
  return `${slug}${LEVEL_KEY_SEPARATOR}${level}`;
}

/** A single axis' filter, matching every goal on that axis. */
export function emptyAxisFilter() {
  return {
    visible: true,
    excludedLevels: [],
    excludedTables: [],
    excludedClearTypes: [],
    excludedRanks: [],
    rateMin: null,
    rateMax: null,
    bpMin: null,
    bpMax: null,
    createdFrom: null,
    createdTo: null,
    achievedFrom: null,
    achievedTo: null,
  };
}

/** Both axes, unfiltered. */
export function emptyGoalFilter() {
  return { applyLevelDisplayPrefs: true, chart: emptyAxisFilter(), course: emptyAxisFilter() };
}

/** Chart and course goals, each keeping their relative input order. */
export function splitGoalsByAxis(goals) {
  const chart = [];
  const course = [];
  for (const goal of goals) {
    if (goal.goal_type === "course") course.push(goal);
    else chart.push(goal);
  }
  return { chart, course };
}

// ── option lists ─────────────────────────────────────────────────────────────

function tableLevelEntries(goal) {
  return (Array.isArray(goal.table_levels) ? goal.table_levels : []).filter(
    (entry) => entry && entry.slug && entry.level,
  );
}

/** Every (table, level) key a goal's chart belongs to. Course goals yield none. */
export function goalLevelKeys(goal) {
  return tableLevelEntries(goal).map((entry) => levelKey(entry.slug, entry.level));
}

function sortedClearTypes(values) {
  // High to low: MAX(9) reads first, matching the clear-distribution legend.
  return [...values].sort((a, b) => b - a);
}

function sortedRanks(values) {
  return [...values].sort((a, b) => (RANK_SORT_ORDER[a] ?? 99) - (RANK_SORT_ORDER[b] ?? 99));
}

function collectScalarOptions(goals) {
  const clearTypes = new Set();
  const ranks = new Set();
  let hasRate = false;
  let hasBp = false;
  for (const goal of goals) {
    if (goal.target_clear_type != null) clearTypes.add(goal.target_clear_type);
    if (goal.target_rank != null) ranks.add(goal.target_rank);
    if (goal.target_rate != null) hasRate = true;
    if (goal.target_min_bp != null) hasBp = true;
  }
  return {
    clearTypes: sortedClearTypes(clearTypes),
    ranks: sortedRanks(ranks),
    hasRate,
    hasBp,
  };
}

function tableIndexBySlug(tables) {
  const index = new Map();
  (tables ?? []).forEach((table, position) => index.set(table.slug, position));
  return index;
}

function tableMetaBySlug(tables) {
  const meta = new Map();
  for (const table of tables ?? []) meta.set(table.slug, table);
  return meta;
}

// Tables the server did not list still get a chip, sorted after the known ones.
function compareBySlugOrder(indexBySlug) {
  return (a, b) => {
    const ia = indexBySlug.has(a) ? indexBySlug.get(a) : Number.POSITIVE_INFINITY;
    const ib = indexBySlug.has(b) ? indexBySlug.get(b) : Number.POSITIVE_INFINITY;
    if (ia !== ib) return ia - ib;
    return a.localeCompare(b);
  };
}

function chartTableOptions(goals, tables) {
  const indexBySlug = tableIndexBySlug(tables);
  const metaBySlug = tableMetaBySlug(tables);

  const levelsBySlug = new Map();
  for (const goal of goals) {
    for (const entry of tableLevelEntries(goal)) {
      if (!levelsBySlug.has(entry.slug)) levelsBySlug.set(entry.slug, new Set());
      levelsBySlug.get(entry.slug).add(entry.level);
    }
  }

  return [...levelsBySlug.keys()]
    .sort(compareBySlugOrder(indexBySlug))
    .map((slug) => {
      const meta = metaBySlug.get(slug);
      const present = levelsBySlug.get(slug);
      const known = (meta?.level_order ?? []).filter((level) => present.has(level));
      const unknown = [...present].filter((level) => !known.includes(level)).sort();
      return {
        slug,
        name: meta?.name ?? slug,
        symbol: meta?.symbol ?? "",
        levels: [...known, ...unknown].map((level) => ({ level, key: levelKey(slug, level) })),
      };
    });
}

function courseTableOptions(goals, tables) {
  const indexBySlug = tableIndexBySlug(tables);
  const metaBySlug = tableMetaBySlug(tables);
  const slugs = new Set();
  for (const goal of goals) {
    if (goal.course_table_slug) slugs.add(goal.course_table_slug);
  }
  return [...slugs].sort(compareBySlugOrder(indexBySlug)).map((slug) => {
    const meta = metaBySlug.get(slug);
    return { slug, name: meta?.name ?? slug, symbol: meta?.symbol ?? "", levels: [] };
  });
}

/**
 * The selectable options actually present in a goal list, per axis, already
 * ordered. `tables` is the server-ordered table block from `GET /goals/`.
 */
export function goalFilterOptions(goals, tables) {
  const { chart, course } = splitGoalsByAxis(goals);
  return {
    chart: {
      goalCount: chart.length,
      tables: chartTableOptions(chart, tables),
      ...collectScalarOptions(chart),
    },
    course: {
      goalCount: course.length,
      tables: courseTableOptions(course, tables),
      ...collectScalarOptions(course),
    },
  };
}

// ── level-display preferences ───────────────────────────────────────────────

function preferenceVisibleTables(tables) {
  const visible = new Map();
  for (const table of tables ?? []) {
    const levelOrder = Array.isArray(table.preference_level_order)
      ? table.preference_level_order
      : table.level_order;
    visible.set(table.slug, {
      table: table.preference_visible !== false,
      levels: new Set(levelOrder ?? []),
    });
  }
  return visible;
}

function preferredTableLevels(goal, visibleBySlug) {
  const entries = tableLevelEntries(goal);
  if (entries.length === 0) return entries;
  const filtered = entries.filter((entry) => {
    const visible = visibleBySlug.get(entry.slug);
    if (!visible) return true;
    return visible.table && visible.levels.has(entry.level);
  });
  return filtered;
}

/**
 * Apply the dashboard user's level-display preference metadata to goal rows.
 *
 * Chart goals keep only preference-visible table-level badges and disappear
 * when all known memberships are hidden. Course goals use their source table's
 * preference visibility. Missing table metadata is treated as visible so stale
 * goals do not vanish because of incomplete enrichment.
 */
export function applyLevelDisplayPreference(goals, tables, enabled) {
  if (!enabled) return goals;
  const visibleBySlug = preferenceVisibleTables(tables);
  return goals.flatMap((goal) => {
    if (goal.goal_type === "course") {
      if (!goal.course_table_slug) return [goal];
      const visible = visibleBySlug.get(goal.course_table_slug);
      return visible && visible.table === false ? [] : [goal];
    }

    const entries = tableLevelEntries(goal);
    if (entries.length === 0) return [goal];
    const table_levels = preferredTableLevels(goal, visibleBySlug);
    return table_levels.length > 0 ? [{ ...goal, table_levels }] : [];
  });
}

// ── matching ─────────────────────────────────────────────────────────────────

// Chip predicates return true when the goal has a value that is still lit, false
// when all of the goal's values for that category are disabled, and null when
// the category does not apply to the goal.
function matchLevels(goal, filter) {
  const keys = goalLevelKeys(goal);
  if (keys.length === 0) return null;
  const disabled = new Set(filter.excludedLevels);
  return keys.some((key) => !disabled.has(key));
}

function matchCourseTable(goal, filter) {
  if (!goal.course_table_slug) return null;
  return !filter.excludedTables.includes(goal.course_table_slug);
}

function matchClear(goal, filter) {
  if (goal.target_clear_type == null) return null;
  return !filter.excludedClearTypes.includes(goal.target_clear_type);
}

function matchRank(goal, filter) {
  if (goal.target_rank == null) return null;
  return !filter.excludedRanks.includes(goal.target_rank);
}

// Ranges are opt-in: typing a bound declares "show me goals that have this
// metric", so a goal without it is excluded rather than neutral.
function matchNumericRange(value, min, max) {
  if (min == null && max == null) return null;
  if (value == null) return null;
  if (min != null && value < min) return false;
  if (max != null && value > max) return false;
  return true;
}

function dateOnly(value) {
  return typeof value === "string" && value.length >= 10 ? value.slice(0, 10) : null;
}

function matchDateRange(value, from, to) {
  if (!from && !to) return null;
  const day = dateOnly(value);
  if (day === null) return false;
  if (from && day < from) return false;
  if (to && day > to) return false;
  return true;
}

/**
 * Whether a goal survives one axis' filter.
 *
 * Table/level and course-table chips are hard visibility gates. Clear/rank are
 * one OR group: a goal carrying HARD+AAA stays visible while either HARD or AAA
 * is lit, and hides only after both are disabled. Numeric/date ranges are hard
 * filters regardless of the chip state.
 */
export function matchesAxisFilter(goal, filter, axis) {
  if (filter.visible === false) return false;

  const levelMatch = axis === "course" ? matchCourseTable(goal, filter) : matchLevels(goal, filter);
  if (levelMatch === false) return false;

  const clearRank = [matchClear(goal, filter), matchRank(goal, filter)].filter(
    (result) => result !== null,
  );
  if (clearRank.length > 0 && !clearRank.some(Boolean)) return false;

  if (matchNumericRange(goal.target_rate, filter.rateMin, filter.rateMax) === false) {
    return false;
  }
  if (matchNumericRange(goal.target_min_bp, filter.bpMin, filter.bpMax) === false) {
    return false;
  }

  if (matchDateRange(goal.created_at, filter.createdFrom, filter.createdTo) === false) {
    return false;
  }
  if (
    matchDateRange(goal.achieved_recorded_at, filter.achievedFrom, filter.achievedTo) === false
  ) {
    return false;
  }
  return true;
}

/** Chart goals against the chart axis, course goals against the course axis. */
export function filterGoals(goals, filter) {
  return goals.filter((goal) =>
    goal.goal_type === "course"
      ? matchesAxisFilter(goal, filter.course, "course")
      : matchesAxisFilter(goal, filter.chart, "chart"),
  );
}

// ── selection helpers ────────────────────────────────────────────────────────

/** A difficulty table is on while any of its level chips is still on. */
export function isTableEnabled(levelKeys, filter) {
  const excluded = new Set(filter.excludedLevels);
  return levelKeys.some((key) => !excluded.has(key));
}

/** Add `value` to the exclusion list, or drop it if already there. */
export function toggleExcluded(list, value) {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

/** Bulk-set the exclusion state of several values at once. */
export function setExcluded(list, values, excluded) {
  if (!excluded) return list.filter((item) => !values.includes(item));
  const missing = values.filter((value) => !list.includes(value));
  return missing.length === 0 ? list : [...list, ...missing];
}

// ── facet counts ─────────────────────────────────────────────────────────────

function axisWithoutCategory(filter, category) {
  switch (category) {
    case "levels":
      return { ...filter, visible: true, excludedLevels: [] };
    case "tables":
      return { ...filter, visible: true, excludedTables: [] };
    case "clearTypes":
      return { ...filter, visible: true, excludedClearTypes: [] };
    default:
      return { ...filter, visible: true, excludedRanks: [] };
  }
}

function countValues(goals, filter, axis, category, valuesOf) {
  const counts = {};
  const reachable = goals.filter((goal) =>
    matchesAxisFilter(goal, axisWithoutCategory(filter, category), axis),
  );
  for (const goal of reachable) {
    for (const value of valuesOf(goal)) {
      counts[value] = (counts[value] ?? 0) + 1;
    }
  }
  return counts;
}

function tableCountsFromLevels(levelCounts, tableOptions) {
  const counts = {};
  for (const table of tableOptions) {
    counts[table.slug] = table.levels.reduce(
      (total, level) => total + (levelCounts[level.key] ?? 0),
      0,
    );
  }
  return counts;
}

/**
 * How many goals each chip would match. A category's counts are computed with
 * that category's own exclusions dropped, so turning a chip back on shows the
 * number of goals it would restore.
 */
export function goalFacetCounts(goals, filter, options) {
  const { chart, course } = splitGoalsByAxis(goals);

  const chartLevels = countValues(chart, filter.chart, "chart", "levels", goalLevelKeys);
  return {
    chart: {
      levels: chartLevels,
      tables: tableCountsFromLevels(chartLevels, options.chart.tables),
      clearTypes: countValues(chart, filter.chart, "chart", "clearTypes", (goal) =>
        goal.target_clear_type == null ? [] : [goal.target_clear_type],
      ),
      ranks: countValues(chart, filter.chart, "chart", "ranks", (goal) =>
        goal.target_rank == null ? [] : [goal.target_rank],
      ),
    },
    course: {
      tables: countValues(course, filter.course, "course", "tables", (goal) =>
        goal.course_table_slug ? [goal.course_table_slug] : [],
      ),
      clearTypes: countValues(course, filter.course, "course", "clearTypes", (goal) =>
        goal.target_clear_type == null ? [] : [goal.target_clear_type],
      ),
      ranks: countValues(course, filter.course, "course", "ranks", (goal) =>
        goal.target_rank == null ? [] : [goal.target_rank],
      ),
    },
  };
}

// ── active state ─────────────────────────────────────────────────────────────

function intersectsOptions(excluded, available) {
  const present = new Set(available);
  return excluded.some((value) => present.has(value));
}

function axisActiveCount(filter, axisOptions) {
  const levelKeysInPlay = axisOptions.tables.flatMap((table) =>
    (table.levels ?? []).map((level) => level.key),
  );
  const tableSlugsInPlay = axisOptions.tables.map((table) => table.slug);

  let count = 0;
  // Exclusions are intersected with the live options: a value whose goals were
  // all deleted no longer narrows anything, and must not show as an active
  // filter the user cannot see or clear.
  if (intersectsOptions(filter.excludedLevels, levelKeysInPlay)) count += 1;
  if (intersectsOptions(filter.excludedTables, tableSlugsInPlay)) count += 1;
  if (intersectsOptions(filter.excludedClearTypes, axisOptions.clearTypes)) count += 1;
  if (intersectsOptions(filter.excludedRanks, axisOptions.ranks)) count += 1;
  if (filter.visible === false && axisOptions.goalCount > 0) count += 1;
  if (filter.rateMin != null || filter.rateMax != null) count += 1;
  if (filter.bpMin != null || filter.bpMax != null) count += 1;
  if (filter.createdFrom || filter.createdTo) count += 1;
  if (filter.achievedFrom || filter.achievedTo) count += 1;
  return count;
}

/** How many dimensions are currently narrowing the list, across both axes. */
export function activeFilterCount(filter, options) {
  return (
    (filter.applyLevelDisplayPrefs === false ? 1 : 0) +
    axisActiveCount(filter.chart, options.chart) +
    axisActiveCount(filter.course, options.course)
  );
}

export function isGoalFilterActive(filter, options) {
  return activeFilterCount(filter, options) > 0;
}
