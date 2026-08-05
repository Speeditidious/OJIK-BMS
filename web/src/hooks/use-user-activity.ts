import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ActivityMetric, ActivityRankingResponse, RecentActivityResponse } from "@/types";

export function useRecentActivity(pageSize = 10, cursor?: string, enabled = true) {
  return useQuery<RecentActivityResponse>({
    queryKey: ["activity", "recent", pageSize, cursor ?? null],
    queryFn: () =>
      api.get(
        `/activity/recent?page_size=${pageSize}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
      ),
    staleTime: 30 * 1000,
    enabled,
  });
}

export function useActivityRanking(metric: ActivityMetric, pageSize = 10, rankAfter = 0, enabled = true) {
  return useQuery<ActivityRankingResponse>({
    queryKey: ["activity", "ranking", metric, pageSize, rankAfter],
    queryFn: () => api.get(`/activity/ranking?metric=${metric}&page_size=${pageSize}&rank_after=${rankAfter}`),
    staleTime: 5 * 60 * 1000,
    enabled,
  });
}
