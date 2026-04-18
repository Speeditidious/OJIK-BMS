import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface UserPublicRead {
  id: string;
  username: string;
  bio: string | null;
  avatar_url: string | null;
  created_at: string;
  last_synced_at: string | null;
}

export function useUserProfile(userId: string) {
  return useQuery({
    queryKey: ["user-profile", userId],
    queryFn: () => api.get<UserPublicRead>(`/users/by-id/${userId}`),
    enabled: !!userId,
  });
}
