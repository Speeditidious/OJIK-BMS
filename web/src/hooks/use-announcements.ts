import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  Announcement,
  AnnouncementTag,
  AnnouncementWrite,
  RenderedAnnouncementTemplate,
  Pagination,
} from "@/types";

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

// ── Admin query hooks ────────────────────────────────────────────────────────

export function useAdminAnnouncements(params: {
  page: number;
  size: number;
  tag?: string;
  published?: boolean;
}) {
  return useQuery<Pagination<Announcement>>({
    queryKey: ["announcements", "admin", params],
    queryFn: () => {
      const search = new URLSearchParams({
        page: String(params.page),
        size: String(params.size),
      });
      if (params.tag) search.set("tag", params.tag);
      if (params.published !== undefined) search.set("published", String(params.published));
      return api.get(`/announcements/admin/?${search.toString()}`);
    },
  });
}

export function useAdminAnnouncement(id: string | null) {
  return useQuery<Announcement>({
    queryKey: ["announcements", "admin", id],
    queryFn: () => api.get(`/announcements/admin/${id}`),
    enabled: id !== null,
  });
}

// ── Admin mutation hooks ─────────────────────────────────────────────────────

export function useCreateAnnouncement() {
  const queryClient = useQueryClient();
  return useMutation<Announcement, Error, AnnouncementWrite>({
    mutationFn: (data) => api.post("/announcements/admin/", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["announcements"] });
      queryClient.invalidateQueries({ queryKey: ["announcements", "latest"] });
      queryClient.invalidateQueries({ queryKey: ["announcements", "admin"] });
    },
  });
}

export function useUpdateAnnouncement() {
  const queryClient = useQueryClient();
  return useMutation<Announcement, Error, { id: string; data: Partial<AnnouncementWrite> }>({
    mutationFn: ({ id, data }) => api.patch(`/announcements/admin/${id}`, data),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["announcements"] });
      queryClient.invalidateQueries({ queryKey: ["announcements", "latest"] });
      queryClient.invalidateQueries({ queryKey: ["announcements", "admin"] });
      queryClient.invalidateQueries({ queryKey: ["announcements", "admin", id] });
    },
  });
}

export function usePublishAnnouncement() {
  const queryClient = useQueryClient();
  return useMutation<Announcement, Error, string>({
    mutationFn: (id) => api.post(`/announcements/admin/${id}/publish`),
    onSuccess: (_result, id) => {
      queryClient.invalidateQueries({ queryKey: ["announcements"] });
      queryClient.invalidateQueries({ queryKey: ["announcements", "latest"] });
      queryClient.invalidateQueries({ queryKey: ["announcements", "admin"] });
      queryClient.invalidateQueries({ queryKey: ["announcements", "admin", id] });
    },
  });
}

// ── Template hooks ────────────────────────────────────────────────────────────

export function useRenderedAnnouncementTemplate(tagId: string | null | undefined) {
  return useQuery<RenderedAnnouncementTemplate>({
    queryKey: ["announcements", "templates", tagId ?? "__global__"],
    queryFn: () => {
      if (tagId === null) {
        return api.get("/announcements/admin/templates");
      }
      return api.get(`/announcements/admin/templates?tag_id=${encodeURIComponent(tagId!)}`);
    },
    enabled: tagId !== undefined,
  });
}

export function useUpsertAnnouncementTemplate() {
  const queryClient = useQueryClient();
  return useMutation<RenderedAnnouncementTemplate, Error, Record<string, unknown>>({
    mutationFn: (data) => api.put("/announcements/admin/templates", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["announcements"] });
      queryClient.invalidateQueries({ queryKey: ["announcements", "latest"] });
      queryClient.invalidateQueries({ queryKey: ["announcements", "admin"] });
      queryClient.invalidateQueries({ queryKey: ["announcements", "templates"] });
    },
  });
}
