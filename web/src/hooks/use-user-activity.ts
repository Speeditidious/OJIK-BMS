import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ActivityMetric, ActivityRange, ActivityRankingResponse, RecentActivityResponse } from "@/types";

export function useRecentActivity(pageSize = 10, page = 1) {
  return useQuery<RecentActivityResponse>({
    queryKey: ["activity", "recent", pageSize, page],
    queryFn: () => api.get(`/activity/recent?page_size=${pageSize}&page=${page}`),
    staleTime: 30 * 1000,
    // Keeps showing the previous page's data while the new page is in
    // flight, instead of resetting `data` to `undefined` (which would
    // otherwise blank the already-rendered list back to a loading skeleton
    // on every page change). Matches the established pattern in
    // `use-rankings.ts`'s `useRankings`.
    placeholderData: keepPreviousData,
  });
}

export function useActivityRanking(
  range: ActivityRange,
  metric: ActivityMetric,
  pageSize = 10,
  page = 1,
) {
  return useQuery<ActivityRankingResponse>({
    queryKey: ["activity", "ranking", range, metric, pageSize, page],
    queryFn: () =>
      api.get(`/activity/ranking?range=${range}&metric=${metric}&page_size=${pageSize}&page=${page}`),
    staleTime: 5 * 60 * 1000,
    // Same rationale as `useRecentActivity` above — avoids a full loading
    // flash when `page` changes.
    placeholderData: keepPreviousData,
  });
}
