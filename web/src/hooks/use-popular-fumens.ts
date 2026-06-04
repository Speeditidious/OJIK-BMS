import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { PopularFumensResponse, PopularRange } from "@/types";

export function usePopularFumens(range: PopularRange, limit = 10) {
  return useQuery<PopularFumensResponse>({
    queryKey: ["popular-fumens", range, limit],
    queryFn: () => api.get(`/fumens/popular?range=${range}&limit=${limit}`),
    staleTime: 5 * 60 * 1000,
  });
}
