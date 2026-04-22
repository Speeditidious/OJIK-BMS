import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { RankingDisplayConfig } from "@/lib/bmsforce-emblem";

const EMPTY_CONFIG: RankingDisplayConfig = { bmsforce_emblems: [] };

/**
 * Fetches ranking display configuration (BMSFORCE emblem tiers) from the backend.
 * Stale after 5 minutes; cached for 30 minutes.
 * On failure, gracefully returns empty emblems array.
 */
export function useRankingDisplayConfig() {
  return useQuery<RankingDisplayConfig>({
    queryKey: ["ranking-display-config"],
    queryFn: async () => {
      try {
        return await api.get<RankingDisplayConfig>("/rankings/display-config");
      } catch {
        return EMPTY_CONFIG;
      }
    },
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    retry: 1,
  });
}
