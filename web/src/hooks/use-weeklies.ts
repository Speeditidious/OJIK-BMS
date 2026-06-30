import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  CategoryMeta,
  WeeklyDetail,
  WeeklyFumenRecords,
  WeeklyPeriodSummary,
  WeeklyRolloverInfo,
} from "@/lib/weekly-types";

export function useWeeklyRolloverInfo() {
  return useQuery<WeeklyRolloverInfo>({
    queryKey: ["weeklies", "rollover-info"],
    queryFn: () => api.get<WeeklyRolloverInfo>("/weeklies/rollover-info"),
    staleTime: 60 * 60 * 1000,
  });
}

export function useWeeklyCategories() {
  return useQuery<CategoryMeta[]>({
    queryKey: ["weeklies", "categories"],
    queryFn: () => api.get<CategoryMeta[]>("/weeklies/categories"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useWeeklyPeriods(categoryKey: string | null, bracketKey: string | null) {
  return useQuery<WeeklyPeriodSummary[]>({
    queryKey: ["weeklies", "periods", categoryKey, bracketKey],
    queryFn: () =>
      api.get<WeeklyPeriodSummary[]>(`/weeklies/${categoryKey}/${bracketKey}/periods`),
    enabled: !!categoryKey && !!bracketKey,
    staleTime: 5 * 60 * 1000,
  });
}

export function useWeeklyDetail(
  categoryKey: string | null,
  bracketKey: string | null,
  offset: number,
) {
  return useQuery<WeeklyDetail>({
    queryKey: ["weeklies", "detail", categoryKey, bracketKey, offset],
    queryFn: () =>
      api.get<WeeklyDetail>(`/weeklies/${categoryKey}/${bracketKey}?offset=${offset}`),
    enabled: !!categoryKey && !!bracketKey,
  });
}

export function useWeeklyFumenRecords(
  weeklyId: string | null,
  fumenId: string | null,
  enabled: boolean,
  offset = 0,
  limit = 50,
  sortKey = "score",
  sortDir = "desc",
) {
  return useQuery<WeeklyFumenRecords>({
    queryKey: ["weeklies", "records", weeklyId, fumenId, offset, limit, sortKey, sortDir],
    queryFn: () =>
      api.get<WeeklyFumenRecords>(
        `/weeklies/${weeklyId}/fumen/${fumenId}/records?limit=${limit}&offset=${offset}&sort_key=${sortKey}&sort_dir=${sortDir}`,
      ),
    enabled: enabled && !!weeklyId && !!fumenId,
  });
}
