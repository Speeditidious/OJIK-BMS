import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ActivityMetric, ActivityRankingResponse, RecentActivityResponse } from "@/types";

export function useRecentActivity(pageSize = 10, cursor?: string) {
  return useQuery<RecentActivityResponse>({
    queryKey: ["activity", "recent", pageSize, cursor ?? null],
    queryFn: () =>
      api.get(
        `/activity/recent?page_size=${pageSize}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
      ),
    staleTime: 30 * 1000,
    // Keeps showing the previous page's data while a new cursor's page is
    // in flight, instead of resetting `data` to `undefined` (which would
    // otherwise blank the already-rendered list back to a loading skeleton
    // on every "load more" click). Matches the established pattern in
    // `use-rankings.ts`'s `useRankingHistory`.
    placeholderData: keepPreviousData,
  });
}

export function useActivityRanking(metric: ActivityMetric, pageSize = 10, rankAfter = 0) {
  return useQuery<ActivityRankingResponse>({
    queryKey: ["activity", "ranking", metric, pageSize, rankAfter],
    queryFn: () => api.get(`/activity/ranking?metric=${metric}&page_size=${pageSize}&rank_after=${rankAfter}`),
    staleTime: 5 * 60 * 1000,
    // Same rationale as `useRecentActivity` above — avoids a full loading
    // flash when `rankAfter` changes on "load more".
    placeholderData: keepPreviousData,
  });
}
