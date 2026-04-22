import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { RatingBreakdownResponse } from "@/lib/ranking-types";
import type { ScoreUpdatesResponse } from "@/types";

export interface PlaySummary {
  total_scores: number;
  total_play_count: number;
  total_playtime: number;
  total_notes_hit: number;
  last_synced_at: string | null;
  first_synced_by_client: Record<string, string | null>;
}

export interface HeatmapDay {
  date: string;      // YYYY-MM-DD
  updates: number;   // rows where at least one metric improved vs previous play (rn > 1)
  new_plays: number; // first-ever plays for a fumen (rn == 1), separate from updates
  plays: number;     // UserPlayerStats.playcount LAG delta sum; first-sync rows = 0
  rating_updates?: number;
}

export interface ActivityDay {
  date: string;
  updates: number;   // rows where at least one metric improved vs previous play (rn > 1)
  new_plays: number; // first-ever plays for a fumen (rn == 1), separate from updates
  plays: number;     // UserPlayerStats.playcount LAG delta sum; first-sync rows = 0
  rating_updates?: number;
}

export interface RecentUpdate {
  id: string;
  fumen_sha256: string | null;
  fumen_md5: string | null;
  fumen_hash_others: string | null;
  client_type: string;
  clear_type: number | null;
  exscore: number | null;
  rate: number | null;
  rank: string | null;
  min_bp: number | null;
  play_count: number | null;
  prev_play_count: number | null;
  is_initial_sync: boolean;
  recorded_at: string | null;
  synced_at: string | null;
  title: string | null;
  artist: string | null;
  difficulty_levels: Array<{ symbol: string; level: string }>;
  is_stat_only: boolean;
}

export interface DaySummary {
  total_updates: number;
  new_plays: number;             // first-ever plays for a fumen on this day
  total_play_count: number | null;  // null = 집계 불가 (첫 동기화 기록 포함)
  play_count_uncertain: boolean;
  stat_only_count: number;
  total_playtime: number;        // seconds; from PlayerStats LAG delta
  total_notes_hit: number;       // notes hit; from PlayerStats judgments LAG delta
  playtime_uncertain: boolean;   // true when first-sync row caused delta=0
  notes_hit_uncertain: boolean;  // true when first-sync row caused delta=0
  rating_updates?: number;
}

export interface RecentUpdatesResponse {
  updates: RecentUpdate[];
  day_summary: DaySummary | null;
}

export interface RatingUpdateEntry {
  rank: number;
  sha256: string | null;
  md5: string | null;
  title: string;
  artist: string | null;
  level: string;
  symbol: string;
  clear_type: number;
  client_types: string[];
  source_client?: string | null;
  source_client_detail?: Record<string, string | null> | null;
  min_bp: number | null;
  rate: number | null;
  rank_grade: string | null;
  exscore: number | null;
  value: number;
  is_in_top_n: boolean;
}

export interface RatingUpdatesResponse {
  table_slug: string;
  calculated_at: string | null;
  date: string | null;
  count: number | null;
  top_n: number;
  dates: Array<{ date: string; count: number }>;
  entries: RatingUpdateEntry[];
}

export interface AggregatedRatingUpdateDay {
  date: string;
  count: number;
}

export interface AggregatedRatingUpdateTable {
  table_slug: string;
  display_name: string;
  count: number;
  display_order: number;
}

export interface AggregatedRatingUpdatesResponse {
  date?: string;
  count?: number;
  dates?: AggregatedRatingUpdateDay[];
  tables?: AggregatedRatingUpdateTable[];
}

export interface GradeDistributionItem {
  clear_type: number | null;
  count: number;
}

export interface TableClearLevel {
  level: string;
  counts: Record<string, number>; // "0" → count, "1" → count, ...
}

export interface TableClearSong {
  sha256: string;
  title: string;
  artist: string;
  level: string;
  clear_type: number; // 0 = NO PLAY
  rate: number | null;
  rank: string | null;
  min_bp: number | null;
  client_type: string | null;
  source_client?: string | null;
  source_client_detail?: Record<string, string | null> | null;
  ex_score: number | null;
  play_count: number | null;
  options: Record<string, unknown> | null;
}

export interface TableClearDistribution {
  table_id: string;
  table_name: string;
  table_symbol: string;
  client_type: string | null;
  levels: TableClearLevel[];
  songs: TableClearSong[];
  level_order: string[];
}

export type ClientTypeFilter = "all" | "lr2" | "beatoraja";

export function usePlaySummary(clientType: ClientTypeFilter = "all", userId?: string, enabled: boolean = true) {
  return useQuery({
    queryKey: ["analysis", "summary", clientType, userId ?? null],
    queryFn: () => {
      const params = new URLSearchParams();
      if (clientType !== "all") params.set("client_type", clientType);
      if (userId) params.set("user_id", userId);
      const suffix = params.size > 0 ? `?${params.toString()}` : "";
      return api.get<PlaySummary>(`/analysis/summary${suffix}`);
    },
    enabled,
    staleTime: 5 * 60 * 1000, // 5 min — changes only on sync
  });
}

export function useActivityHeatmap(
  year: number = 0,
  clientType: ClientTypeFilter = "all",
  userId?: string,
  enabled: boolean = true,
) {
  return useQuery({
    queryKey: ["analysis", "heatmap", year, clientType, userId ?? null],
    queryFn: () => {
      const params = new URLSearchParams({ year: String(year) });
      if (clientType !== "all") params.set("client_type", clientType);
      if (userId) params.set("user_id", userId);
      return api.get<{ year: number; data: HeatmapDay[] }>(`/analysis/heatmap?${params}`);
    },
    enabled,
    staleTime: 30 * 60 * 1000, // 30 min — historical data
  });
}

export type ActivityBarMode =
  | { kind: "days"; days: number }
  | { kind: "range"; from: string; to: string };

export interface ActivityBarArgs {
  mode?: ActivityBarMode;
  clientType?: ClientTypeFilter;
  userId?: string;
  enabled?: boolean;
}

export function useActivityBar(argsOrDays: ActivityBarArgs | number = {}, clientTypeOrUndef?: ClientTypeFilter, userIdOrUndef?: string) {
  // Support both legacy call signature (days, clientType, userId) and new object form
  const args: ActivityBarArgs = typeof argsOrDays === "number"
    ? { mode: { kind: "days", days: argsOrDays }, clientType: clientTypeOrUndef, userId: userIdOrUndef }
    : argsOrDays;

  const mode: ActivityBarMode = args.mode ?? { kind: "days", days: 30 };
  const clientType: ClientTypeFilter = args.clientType ?? "all";
  const userId = args.userId;
  const enabled = args.enabled ?? true;

  const modeKey = mode.kind === "days" ? ["days", mode.days] : ["range", mode.from, mode.to];

  return useQuery({
    queryKey: ["analysis", "activity", ...modeKey, clientType, userId ?? null],
    queryFn: () => {
      const params = new URLSearchParams();
      if (mode.kind === "days") {
        params.set("days", String(mode.days));
      } else {
        params.set("from", mode.from);
        params.set("to", mode.to);
      }
      if (clientType !== "all") params.set("client_type", clientType);
      if (userId) params.set("user_id", userId);
      return api.get<{ days?: number; from?: string; to?: string; data: ActivityDay[] }>(`/analysis/activity?${params}`);
    },
    enabled,
    staleTime: 60 * 1000, // 1 min
    placeholderData: (prev) => prev,
    gcTime: 5 * 60 * 1000,
  });
}

export function useRecentUpdates(
  limit: number = 20,
  clientType: ClientTypeFilter = "all",
  date?: string,
  tableSlug?: string | null,
  userId?: string,
) {
  return useQuery({
    queryKey: ["analysis", "recent-updates", limit, clientType, date ?? null, tableSlug ?? null, userId ?? null],
    queryFn: () => {
      const params = new URLSearchParams({ limit: String(limit) });
      if (clientType !== "all") params.set("client_type", clientType);
      if (date) params.set("date", date);
      if (tableSlug) params.set("table_slug", tableSlug);
      if (userId) params.set("user_id", userId);
      return api.get<RecentUpdatesResponse>(`/analysis/recent-updates?${params}`);
    },
    staleTime: 2 * 60 * 1000, // 2 min — more volatile
  });
}

interface RatingUpdatesParams {
  tableSlug: string | null;
  year?: number;
  days?: number;
  date?: string;
  from?: string;
  to?: string;
  userId?: string;
}

export function useRatingUpdates({ tableSlug, year, days, date, from, to, userId }: RatingUpdatesParams) {
  const hasRange = from !== undefined && to !== undefined;
  return useQuery({
    queryKey: ["analysis", "rating-updates", tableSlug, year ?? null, days ?? null, date ?? null, from ?? null, to ?? null, userId ?? null],
    queryFn: () => {
      const params = new URLSearchParams({ table_slug: tableSlug! });
      if (year !== undefined) params.set("year", String(year));
      if (days !== undefined) params.set("days", String(days));
      if (date) params.set("date", date);
      if (from) params.set("from", from);
      if (to) params.set("to", to);
      if (userId) params.set("user_id", userId);
      return api.get<RatingUpdatesResponse>(`/analysis/rating-updates?${params.toString()}`);
    },
    enabled: !!tableSlug && (hasRange
      ? true
      : [year, days, date].filter((value) => value !== undefined && value !== null).length === 1),
    staleTime: 60 * 1000,
    placeholderData: (prev) => prev,
    gcTime: 5 * 60 * 1000,
  });
}

interface AggregatedRatingUpdatesParams {
  year?: number;
  days?: number;
  date?: string;
  from?: string;
  to?: string;
  userId?: string;
  enabled?: boolean;
}

export function useAggregatedRatingUpdates({ year, days, date, from, to, userId, enabled = true }: AggregatedRatingUpdatesParams) {
  const hasRange = from !== undefined && to !== undefined;
  return useQuery({
    queryKey: ["analysis", "rating-updates-aggregated", year ?? null, days ?? null, date ?? null, from ?? null, to ?? null, userId ?? null],
    queryFn: () => {
      const params = new URLSearchParams();
      if (year !== undefined) params.set("year", String(year));
      if (days !== undefined) params.set("days", String(days));
      if (date) params.set("date", date);
      if (from) params.set("from", from);
      if (to) params.set("to", to);
      if (userId) params.set("user_id", userId);
      return api.get<AggregatedRatingUpdatesResponse>(
        `/analysis/rating-updates/aggregated?${params.toString()}`,
      );
    },
    enabled: enabled && (
      hasRange
        ? true
        : [year, days, date].filter((value) => value !== undefined && value !== null).length === 1
    ),
    staleTime: 60 * 1000,
    placeholderData: (prev) => prev,
    gcTime: 5 * 60 * 1000,
  });
}

interface RatingBreakdownParams {
  tableSlug: string | null;
  date?: string;
  userId?: string;
  enabled?: boolean;
}

export function useRatingBreakdown({ tableSlug, date, userId, enabled = true }: RatingBreakdownParams) {
  return useQuery({
    queryKey: ["analysis", "rating-breakdown", tableSlug, date ?? null, userId ?? null],
    queryFn: () => {
      const params = new URLSearchParams({ table_slug: tableSlug!, date: date! });
      if (userId) params.set("user_id", userId);
      return api.get<RatingBreakdownResponse>(
        `/analysis/rating-breakdown?${params.toString()}`,
      );
    },
    enabled: enabled && !!tableSlug && !!date,
    staleTime: 5 * 60 * 1000,
  });
}

export interface NotesActivityDay {
  date: string;
  notes: number;
  plays: number;
}

export interface CourseActivityItem {
  date: string; // YYYY-MM-DD
  course_hash: string;
  clear_type: number | null;
  client_type: string;
  course_name: string | null;
  dan_title: string | null;
  song_count: number | null;
}

export function useNotesActivity(days: number = 90, date?: string) {
  return useQuery({
    queryKey: ["analysis", "notes-activity", days, date ?? null],
    queryFn: () => {
      const params = new URLSearchParams({ days: String(days) });
      if (date) params.set("date", date);
      return api.get<NotesActivityDay[]>(`/analysis/notes-activity?${params}`);
    },
    staleTime: 5 * 60 * 1000, // 5 min
  });
}

export function useCourseActivity(
  year?: number,
  days?: number,
  clientType?: ClientTypeFilter,
  date?: string,
  userId?: string,
  enabled: boolean = true,
) {
  return useQuery({
    queryKey: ["analysis", "course-activity", year ?? null, days ?? null, clientType ?? "all", date ?? null, userId ?? null],
    queryFn: () => {
      const params = new URLSearchParams();
      if (year) params.set("year", String(year));
      if (days) params.set("days", String(days));
      if (clientType && clientType !== "all") params.set("client_type", clientType);
      if (date) params.set("date", date);
      if (userId) params.set("user_id", userId);
      return api.get<CourseActivityItem[]>(`/analysis/course-activity?${params}`);
    },
    enabled,
    staleTime: 30 * 60 * 1000,
  });
}

export function useGradeDistribution(clientType?: string, userId?: string) {
  return useQuery({
    queryKey: ["analysis", "grade-distribution", clientType, userId ?? null],
    queryFn: () => {
      const params = new URLSearchParams();
      if (clientType) params.set("client_type", clientType);
      if (userId) params.set("user_id", userId);
      const suffix = params.size > 0 ? `?${params.toString()}` : "";
      return api.get<{ distribution: GradeDistributionItem[] }>(
        `/analysis/grade-distribution${suffix}`
      );
    },
    staleTime: 10 * 60 * 1000, // 10 min
  });
}

export function useTableClearDistribution(tableId: string | null, clientType?: string, userId?: string) {
  return useQuery({
    queryKey: ["analysis", "table-clear-distribution", tableId, clientType, userId ?? null],
    queryFn: () => {
      const params = new URLSearchParams();
      if (clientType) params.set("client_type", clientType);
      if (userId) params.set("user_id", userId);
      const suffix = params.size > 0 ? `?${params.toString()}` : "";
      return api.get<TableClearDistribution>(
        `/analysis/table/${tableId}/clear-distribution${suffix}`
      );
    },
    enabled: tableId !== null,
    staleTime: 10 * 60 * 1000, // 10 min
  });
}

export function useScoreUpdates(
  clientType?: ClientTypeFilter,
  date?: string,
  limit: number = 50,
  userId?: string,
) {
  return useQuery({
    queryKey: ["analysis", "score-updates", clientType ?? "all", date ?? null, limit, userId ?? null],
    queryFn: () => {
      const params = new URLSearchParams({ limit: String(limit) });
      if (clientType && clientType !== "all") params.set("client_type", clientType);
      if (date) params.set("date", date);
      if (userId) params.set("user_id", userId);
      return api.get<ScoreUpdatesResponse>(`/analysis/score-updates?${params}`);
    },
    staleTime: 2 * 60 * 1000, // 2 min
  });
}
