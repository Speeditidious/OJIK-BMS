import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface PlaySummary {
  total_scores: number;
  total_play_count: number;
  total_notes: number;
  last_synced_at: string | null;
  first_synced_by_client: Record<string, string | null>;
}

export interface HeatmapDay {
  date: string; // YYYY-MM-DD
  value: number;
}

export interface ActivityDay {
  date: string;
  updates: number;
}

export interface RecentUpdate {
  id: string;
  song_sha256: string | null;
  song_md5: string | null;
  client_type: string;
  clear_type: number | null;
  old_clear_type: number | null;
  score: number | null;
  old_score: number | null;
  score_rate: number | null;
  old_score_rate: number | null;
  min_bp: number | null;
  old_min_bp: number | null;
  recorded_at: string | null;
  played_at: string | null;
  sync_date: string | null;
  title: string | null;
  subtitle: string | null;
  artist: string | null;
  difficulty_levels: Array<{ symbol: string; level: string }>;
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
  score_rate: number | null;
  min_bp: number | null;
  client_type: string | null;
  ex_score: number | null;
  options: Record<string, unknown> | null;
}

export interface TableClearDistribution {
  table_id: number;
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
      return api.get<{ updates: RecentUpdate[] }>(`/analysis/recent-updates?${params}`);
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
  old_clear_type: number | null;
  is_first_clear: boolean;
}

export function useNotesActivity(days: number = 90) {
  return useQuery({
    queryKey: ["analysis", "notes-activity", days],
    queryFn: () => {
      const params = new URLSearchParams({ days: String(days) });
      return api.get<NotesActivityDay[]>(`/analysis/notes-activity?${params}`);
    },
    staleTime: 5 * 60 * 1000, // 5 min
  });
}

export function useCourseActivity(
  year?: number,
  days?: number,
  clientType?: ClientTypeFilter
) {
  return useQuery({
    queryKey: ["analysis", "course-activity", year ?? null, days ?? null, clientType ?? "all"],
    queryFn: () => {
      const params = new URLSearchParams();
      if (year) params.set("year", String(year));
      if (days) params.set("days", String(days));
      if (clientType && clientType !== "all") params.set("client_type", clientType);
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

export function useTableClearDistribution(tableId: number | null, clientType?: string) {
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
