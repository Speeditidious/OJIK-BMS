import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { CourseRowDetailResponse } from "@/lib/score-row-detail-types";

interface UseCourseRowDetailParams {
  courseHash: string | null | undefined;
  clientType: string | null | undefined;
  scoreId?: string | null;
  userId?: string | null;
  asOf?: string | null;
  enabled?: boolean;
}

/** Fetch the lazy aggregate detail payload for one course score row. */
export function useCourseRowDetail({
  courseHash,
  clientType,
  scoreId,
  userId,
  asOf,
  enabled = true,
}: UseCourseRowDetailParams): UseQueryResult<CourseRowDetailResponse> {
  return useQuery<CourseRowDetailResponse>({
    queryKey: ["courseRowDetail", courseHash ?? null, clientType ?? null, scoreId ?? null, userId ?? null, asOf ?? null],
    queryFn: () => {
      const params = new URLSearchParams({ client_type: clientType! });
      if (userId) params.set("user_id", userId);
      if (asOf) params.set("as_of", asOf);
      if (scoreId) params.set("score_id", scoreId);
      return api.get<CourseRowDetailResponse>(
        `/scores/course/${encodeURIComponent(courseHash!)}/row-detail?${params}`,
      );
    },
    enabled: enabled && !!courseHash && !!clientType,
    staleTime: 5 * 60 * 1000,
  });
}
