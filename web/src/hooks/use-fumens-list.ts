import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { FumenListResponse, FumenSearchField } from "@/types";

interface UseFumensListParams {
  field: FumenSearchField;
  q: string;
  page: number;
  sortBy?: string;
  sortDir?: "asc" | "desc";
  limit?: number;
}

export function useFumensList({
  field,
  q,
  page,
  sortBy = "title",
  sortDir = "asc",
  limit = 50,
}: UseFumensListParams) {
  return useQuery<FumenListResponse>({
    queryKey: ["fumens-list", field, q, page, sortBy, sortDir, limit],
    queryFn: () => {
      const params = new URLSearchParams({
        field,
        page: String(page),
        limit: String(limit),
        sort_by: sortBy,
        sort_dir: sortDir,
      });
      if (q.trim()) params.set("q", q.trim());
      return api.get<FumenListResponse>(`/fumens/?${params.toString()}`);
    },
    staleTime: 60 * 1000,
  });
}
