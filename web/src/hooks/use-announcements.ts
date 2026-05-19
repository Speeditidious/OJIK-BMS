import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Announcement, AnnouncementTag, Pagination } from "@/types";

export function useAnnouncements(params: { page: number; size: number; tag?: string }) {
  return useQuery<Pagination<Announcement>>({
    queryKey: ["announcements", params],
    queryFn: () => {
      const search = new URLSearchParams({
        page: String(params.page),
        size: String(params.size),
      });
      if (params.tag) search.set("tag", params.tag);
      return api.get(`/announcements/?${search.toString()}`);
    },
  });
}

export function useLatestAnnouncement() {
  return useQuery<Announcement | null>({
    queryKey: ["announcements", "latest"],
    queryFn: () => api.get("/announcements/latest"),
  });
}

export function useAnnouncementTags() {
  return useQuery<AnnouncementTag[]>({
    queryKey: ["announcements", "tags"],
    queryFn: () => api.get("/announcements/tags"),
  });
}
