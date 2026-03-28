import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { FumenDetail } from "@/types";

export function useFumenDetail(hash: string | null) {
  return useQuery<FumenDetail>({
    queryKey: ["fumen", hash],
    queryFn: () => api.get(`/fumens/${hash}`),
    enabled: !!hash,
    staleTime: 10 * 60 * 1000,
  });
}
