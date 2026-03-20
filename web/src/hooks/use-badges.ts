import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface DanBadge {
  dan_course_id: number;
  course_hash: string;
  name: string;
  short_name: string | null;
  category: string | null;
  clear_type: number;
  client_type: string;
  achieved_at: string;
}

export function useDanBadges() {
  return useQuery({
    queryKey: ["users", "me", "badges"],
    queryFn: () => api.get<DanBadge[]>("/users/me/badges"),
    staleTime: 10 * 60 * 1000, // 10 min
  });
}
