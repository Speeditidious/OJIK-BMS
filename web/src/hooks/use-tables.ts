import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface DifficultyTableItem {
  id: number;
  name: string;
  symbol: string | null;
  slug: string | null;
  source_url: string | null;
  is_default: boolean;
  last_synced_at: string | null;
  song_count: number | null;
}

export function useFavoriteTables() {
  return useQuery({
    queryKey: ["tables", "favorites"],
    queryFn: () => api.get<DifficultyTableItem[]>("/tables/favorites/me"),
  });
}
