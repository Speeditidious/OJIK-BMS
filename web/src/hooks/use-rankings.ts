import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  MyRankData,
  RankingContributionResponse,
  RatingContributionMetric,
  RatingContributionScope,
  RatingContributionSortBy,
  RankingHistoryResponse,
  RankingResponse,
  RankingTableConfig,
  RankingType,
} from "@/lib/ranking-types";

// Backend sends rating_norm; map to bms_force for frontend branding.
function mapMyRankData(raw: any): MyRankData {
  return {
    ...raw,
    bms_force: raw.rating_norm ?? 0,
    bms_force_rank: raw.rating_norm_rank ?? null,
    bms_force_total_users: raw.rating_norm_total_users ?? 0,
  };
}

export function useRankingTables() {
  return useQuery<RankingTableConfig[]>({
    queryKey: ["ranking-tables"],
    queryFn: async () => {
      const tables = await api.get<RankingTableConfig[]>("/rankings/tables");
      return [...tables].sort((left, right) => left.display_order - right.display_order);
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useRankings(
  tableSlug: string | null,
  type: RankingType,
  page: number,
  limit = 50,
) {
  return useQuery<RankingResponse>({
    queryKey: ["rankings", tableSlug, type, page, limit],
    queryFn: () =>
      api.get<RankingResponse>(
        `/rankings/${tableSlug}?type=${type}&page=${page}&limit=${limit}`,
      ),
    enabled: !!tableSlug,
    staleTime: 60 * 1000,
  });
}

export function useMyRank(tableSlug: string | null, userId?: string | null, enabled: boolean = true) {
  return useQuery<MyRankData>({
    queryKey: ["my-rank", tableSlug, userId ?? null],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (userId) {
        params.set("user_id", userId);
      }
      const suffix = params.size > 0 ? `?${params.toString()}` : "";
      const raw = await api.get<any>(`/rankings/${tableSlug}/me${suffix}`);
      return mapMyRankData(raw);
    },
    enabled: enabled && !!tableSlug,
    staleTime: 60 * 1000,
    retry: false,
  });
}

export function useRankingHistory(
  tableSlug: string | null,
  from: string | null,
  to: string | null,
  userId?: string | null,
  enabled: boolean = true,
) {
  return useQuery<RankingHistoryResponse>({
    queryKey: ["ranking-history", tableSlug, from, to, userId ?? null],
    queryFn: () => {
      const params = new URLSearchParams({ from: from!, to: to! });
      if (userId) {
        params.set("user_id", userId);
      }
      return api.get<RankingHistoryResponse>(
        `/rankings/${tableSlug}/history?${params.toString()}`,
      );
    },
    enabled: enabled && !!tableSlug && !!from && !!to,
    staleTime: 5 * 60 * 1000,
    placeholderData: keepPreviousData,
  });
}

interface RankingContributionParams {
  tableSlug: string | null;
  metric: RatingContributionMetric;
  scope: RatingContributionScope;
  sortBy: RatingContributionSortBy;
  sortDir: "asc" | "desc";
  page?: number;
  limit?: number;
  query?: string;
  userId?: string | null;
  enabled?: boolean;
}

export function useRankingContributionRows({
  tableSlug,
  metric,
  scope,
  sortBy,
  sortDir,
  page = 1,
  limit = 100,
  query = "",
  userId,
  enabled = true,
}: RankingContributionParams) {
  return useQuery<RankingContributionResponse>({
    queryKey: [
      "ranking-contributions",
      tableSlug,
      metric,
      scope,
      sortBy,
      sortDir,
      page,
      limit,
      query,
      userId ?? null,
    ],
    queryFn: () => {
      const params = new URLSearchParams({
        metric,
        scope,
        sort_by: sortBy,
        sort_dir: sortDir,
        page: String(page),
        limit: String(limit),
      });
      if (query.trim()) {
        params.set("query", query.trim());
      }
      if (userId) {
        params.set("user_id", userId);
      }
      return api.get<RankingContributionResponse>(
        `/rankings/${tableSlug}/me/contributions?${params.toString()}`,
      );
    },
    enabled: enabled && !!tableSlug,
    staleTime: 60 * 1000,
    placeholderData: (previousData, previousQuery) => {
      if (!previousQuery || !previousData) return undefined;
      const previousTableSlug = previousQuery.queryKey[1];
      return previousTableSlug === tableSlug ? previousData : undefined;
    },
  });
}
