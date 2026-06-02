import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { FumenRowDetailResponse } from "@/lib/score-row-detail-types";

interface UseScoreRowDetailParams {
  fumenId: string | null | undefined;
  scoreId?: string | null;
  userId?: string | null;
  asOf?: string | null;
  enabled?: boolean;
}

/**
 * Fetches the lazy row-detail payload for a fumen.
 *
 * @param params.fumenId  - The fumen UUID to look up.
 * @param params.userId   - Optional user UUID to scope results.
 * @param params.asOf     - Optional ISO date string (YYYY-MM-DD) snapshot cutoff.
 * @param params.enabled  - Set to false to suspend fetching (default: true).
 */
export function useScoreRowDetail({
  fumenId,
  scoreId,
  userId,
  asOf,
  enabled = true,
}: UseScoreRowDetailParams): UseQueryResult<FumenRowDetailResponse> {
  return useQuery<FumenRowDetailResponse>({
    queryKey: ["scoreRowDetail", scoreId ? "score" : "fumen", scoreId ?? fumenId ?? null, userId ?? null, asOf ?? null],
    queryFn: () => {
      const params = new URLSearchParams();
      if (userId) params.set("user_id", userId);
      if (asOf)   params.set("as_of", asOf);
      const qs = params.toString();
      const path = scoreId
        ? `/scores/row/${scoreId}/row-detail`
        : `/scores/fumen/${fumenId}/row-detail`;
      return api.get<FumenRowDetailResponse>(`${path}${qs ? `?${qs}` : ""}`);
    },
    enabled: enabled && (!!scoreId || !!fumenId),
    staleTime: 5 * 60 * 1000,
  });
}
