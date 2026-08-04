export type GoalAxis = "chart" | "course";

export interface GoalTableLevel {
  slug: string;
  symbol: string;
  level: string;
}

/** The server-ordered table block from `GET /goals/`. */
export interface GoalTable {
  slug: string;
  name: string;
  symbol: string;
  level_order: string[];
  /** Whether this table is visible under the dashboard user's level-display preferences. */
  preference_visible?: boolean;
  /** Levels visible under level-display preferences; omitted by older responses. */
  preference_level_order?: string[];
}

export interface AxisFilter {
  visible: boolean;
  excludedLevels: string[];
  excludedTables: string[];
  excludedClearTypes: number[];
  excludedRanks: string[];
  rateMin: number | null;
  rateMax: number | null;
  bpMin: number | null;
  bpMax: number | null;
  createdFrom: string | null;
  createdTo: string | null;
  achievedFrom: string | null;
  achievedTo: string | null;
}

export interface GoalFilter {
  applyLevelDisplayPrefs: boolean;
  chart: AxisFilter;
  course: AxisFilter;
}

export interface TableLevelOption {
  level: string;
  key: string;
}

export interface TableOption {
  slug: string;
  name: string;
  symbol: string;
  /** Empty on the course axis — courses have no level. */
  levels: TableLevelOption[];
}

export interface AxisOptions {
  goalCount: number;
  tables: TableOption[];
  clearTypes: number[];
  ranks: string[];
  hasRate: boolean;
  hasBp: boolean;
}

export interface GoalFilterOptions {
  chart: AxisOptions;
  course: AxisOptions;
}

export interface AxisFacetCounts {
  levels?: Record<string, number>;
  tables: Record<string, number>;
  clearTypes: Record<number, number>;
  ranks: Record<string, number>;
}

export interface GoalFacetCounts {
  chart: AxisFacetCounts;
  course: AxisFacetCounts;
}

interface FilterableGoal {
  goal_type: "chart" | "course";
  target_clear_type: number | null;
  target_min_bp: number | null;
  target_rank: string | null;
  target_rate: number | null;
  created_at: string | null;
  achieved_recorded_at: string | null;
  table_levels: GoalTableLevel[];
  course_table_slug: string | null;
}

export function levelKey(slug: string, level: string): string;
export function emptyAxisFilter(): AxisFilter;
export function emptyGoalFilter(): GoalFilter;
export function splitGoalsByAxis<T extends FilterableGoal>(goals: T[]): { chart: T[]; course: T[] };
export function goalLevelKeys(goal: FilterableGoal): string[];
export function goalFilterOptions(goals: FilterableGoal[], tables: GoalTable[]): GoalFilterOptions;
export function applyLevelDisplayPreference<T extends FilterableGoal>(
  goals: T[],
  tables: GoalTable[],
  enabled: boolean,
): T[];
export function matchesAxisFilter(goal: FilterableGoal, filter: AxisFilter, axis: GoalAxis): boolean;
export function filterGoals<T extends FilterableGoal>(goals: T[], filter: GoalFilter): T[];
export function isTableEnabled(levelKeys: string[], filter: AxisFilter): boolean;
export function toggleExcluded<T>(list: T[], value: T): T[];
export function setExcluded<T>(list: T[], values: T[], excluded: boolean): T[];
export function goalFacetCounts(
  goals: FilterableGoal[],
  filter: GoalFilter,
  options: GoalFilterOptions,
): GoalFacetCounts;
export function activeFilterCount(filter: GoalFilter, options: GoalFilterOptions): number;
export function isGoalFilterActive(filter: GoalFilter, options: GoalFilterOptions): boolean;
