import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

export interface DifficultyTableItem {
  id: string;
  name: string;
  symbol: string | null;
  slug: string | null;
  source_url: string | null;
  is_default: boolean;
  updated_at: string;
  song_count: number | null;
}

export function useFavoriteTables() {
  const { isInitialized, user } = useAuthStore();
  return useQuery({
    queryKey: ["tables", "favorites"],
    queryFn: () => api.get<DifficultyTableItem[]>("/tables/favorites/me"),
    enabled: isInitialized && !!user,
  });
}
