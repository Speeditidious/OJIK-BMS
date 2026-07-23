import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useLevelDisplayPrefs } from "@/hooks/use-preferences";
import type { FumenListResponse, FumenSearchField, FumenSearchMode } from "@/types";

interface UseFumensListParams {
  field: FumenSearchField;
  q: string;
  searchMode?: FumenSearchMode;
  page: number;
  sortBy?: string;
  sortDir?: "asc" | "desc";
  limit?: number;
  enabled?: boolean;
}

export function useFumensList({
  field,
  q,
  searchMode = "basic",
  page,
  sortBy = "title",
  sortDir = "asc",
  limit = 50,
  enabled = true,
}: UseFumensListParams) {
  const levelDisplayPrefs = useLevelDisplayPrefs();

  return useQuery<FumenListResponse>({
    queryKey: [
      "fumens-list",
      field,
      q,
      searchMode,
      page,
      sortBy,
      sortDir,
      limit,
      levelDisplayPrefs.favorite,
      levelDisplayPrefs.server_default,
      levelDisplayPrefs.user_added,
      levelDisplayPrefs.ojik_custom,
      levelDisplayPrefs.favorite_show_non_regular,
      levelDisplayPrefs.server_default_show_non_regular,
      levelDisplayPrefs.user_added_show_non_regular,
      levelDisplayPrefs.ojik_custom_show_non_regular,
    ],
    queryFn: () => {
      const params = new URLSearchParams({
        field,
        page: String(page),
        limit: String(limit),
        sort_by: sortBy,
        sort_dir: sortDir,
        search_mode: searchMode,
      });
      if (q.trim()) params.set("q", q.trim());
      return api.get<FumenListResponse>(`/fumens/?${params.toString()}`);
    },
    enabled,
    staleTime: 60 * 1000,
  });
}
