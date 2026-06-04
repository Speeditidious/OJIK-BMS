import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { PopularFumensResponse, PopularRange, PopularSortBy } from "@/types";

export function usePopularFumens(range: PopularRange, limit = 10, sortBy: PopularSortBy = "players") {
  return useQuery<PopularFumensResponse>({
    queryKey: ["popular-fumens", range, limit, sortBy],
    queryFn: () => api.get(`/fumens/popular?range=${range}&limit=${limit}&sort_by=${sortBy}`),
    staleTime: 5 * 60 * 1000,
  });
}
