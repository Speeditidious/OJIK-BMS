import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
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
  date: string; // YYYY-MM-DD
  updates: number; // rows where at least one metric improved vs previous play
  plays: number;   // UserPlayerStats.playcount LAG delta sum; first-sync rows = 0
}

export interface ActivityDay {
  date: string;
  updates: number; // rows where at least one metric improved vs previous play
  plays: number;   // UserPlayerStats.playcount LAG delta sum; first-sync rows = 0
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
  total_play_count: number | null;  // null = 집계 불가 (첫 동기화 기록 포함)
  play_count_uncertain: boolean;
  stat_only_count: number;
  total_playtime: number;        // seconds; from PlayerStats LAG delta
  total_notes_hit: number;       // notes hit; from PlayerStats judgments LAG delta
  playtime_uncertain: boolean;   // true when first-sync row caused delta=0
  notes_hit_uncertain: boolean;  // true when first-sync row caused delta=0
}

export interface RecentUpdatesResponse {
  updates: RecentUpdate[];
  day_summary: DaySummary | null;
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

export function usePlaySummary(clientType: ClientTypeFilter = "all") {
  return useQuery({
    queryKey: ["analysis", "summary", clientType],
    queryFn: () => {
      const params = clientType !== "all" ? `?client_type=${clientType}` : "";
      return api.get<PlaySummary>(`/analysis/summary${params}`);
    },
    staleTime: 5 * 60 * 1000, // 5 min — changes only on sync
  });
}

export function useActivityHeatmap(year: number = 0, clientType: ClientTypeFilter = "all") {
  return useQuery({
    queryKey: ["analysis", "heatmap", year, clientType],
    queryFn: () => {
      const params = new URLSearchParams({ year: String(year) });
      if (clientType !== "all") params.set("client_type", clientType);
      return api.get<{ year: number; data: HeatmapDay[] }>(`/analysis/heatmap?${params}`);
    },
    staleTime: 30 * 60 * 1000, // 30 min — historical data
  });
}

export function useActivityBar(days: number = 30, clientType: ClientTypeFilter = "all") {
  return useQuery({
    queryKey: ["analysis", "activity", days, clientType],
    queryFn: () => {
      const params = new URLSearchParams({ days: String(days) });
      if (clientType !== "all") params.set("client_type", clientType);
      return api.get<{ days: number; data: ActivityDay[] }>(`/analysis/activity?${params}`);
    },
    staleTime: 5 * 60 * 1000, // 5 min — changes only on sync
  });
}

export function useRecentUpdates(
  limit: number = 20,
  clientType: ClientTypeFilter = "all",
  date?: string
) {
  return useQuery({
    queryKey: ["analysis", "recent-updates", limit, clientType, date ?? null],
    queryFn: () => {
      const params = new URLSearchParams({ limit: String(limit) });
      if (clientType !== "all") params.set("client_type", clientType);
      if (date) params.set("date", date);
      return api.get<RecentUpdatesResponse>(`/analysis/recent-updates?${params}`);
    },
    staleTime: 2 * 60 * 1000, // 2 min — more volatile
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
  date?: string
) {
  return useQuery({
    queryKey: ["analysis", "course-activity", year ?? null, days ?? null, clientType ?? "all", date ?? null],
    queryFn: () => {
      const params = new URLSearchParams();
      if (year) params.set("year", String(year));
      if (days) params.set("days", String(days));
      if (clientType && clientType !== "all") params.set("client_type", clientType);
      if (date) params.set("date", date);
      return api.get<CourseActivityItem[]>(`/analysis/course-activity?${params}`);
    },
    staleTime: 30 * 60 * 1000,
  });
}

export function useGradeDistribution(clientType?: string) {
  return useQuery({
    queryKey: ["analysis", "grade-distribution", clientType],
    queryFn: () => {
      const params = clientType ? `?client_type=${clientType}` : "";
      return api.get<{ distribution: GradeDistributionItem[] }>(
        `/analysis/grade-distribution${params}`
      );
    },
    staleTime: 10 * 60 * 1000, // 10 min
  });
}

export function useTableClearDistribution(tableId: string | null, clientType?: string) {
  return useQuery({
    queryKey: ["analysis", "table-clear-distribution", tableId, clientType],
    queryFn: () => {
      const params = clientType ? `?client_type=${clientType}` : "";
      return api.get<TableClearDistribution>(
        `/analysis/table/${tableId}/clear-distribution${params}`
      );
    },
    enabled: tableId !== null,
    staleTime: 10 * 60 * 1000, // 10 min
  });
}

export function useScoreUpdates(
  clientType?: ClientTypeFilter,
  date?: string,
  limit: number = 50
) {
  return useQuery({
    queryKey: ["analysis", "score-updates", clientType ?? "all", date ?? null, limit],
    queryFn: () => {
      const params = new URLSearchParams({ limit: String(limit) });
      if (clientType && clientType !== "all") params.set("client_type", clientType);
      if (date) params.set("date", date);
      return api.get<ScoreUpdatesResponse>(`/analysis/score-updates?${params}`);
    },
    staleTime: 2 * 60 * 1000, // 2 min
  });
}
