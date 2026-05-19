import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { NotificationItem, Pagination } from "@/types";

export function useNotifications(params: {
  page: number;
  size: number;
  type?: string;
  keyword?: string;
  dateFrom?: string;
  dateTo?: string;
  unreadOnly?: boolean;
}) {
  return useQuery<Pagination<NotificationItem>>({
    queryKey: ["notifications", params],
    queryFn: () => {
      const search = new URLSearchParams({
        page: String(params.page),
        size: String(params.size),
      });
      if (params.type) search.set("type", params.type);
      if (params.keyword) search.set("keyword", params.keyword);
      if (params.dateFrom) search.set("date_from", params.dateFrom);
      if (params.dateTo) search.set("date_to", params.dateTo);
      if (params.unreadOnly) search.set("unread_only", "true");
      return api.get(`/notifications/?${search.toString()}`);
    },
  });
}

export function useUnreadCount(enabled: boolean) {
  return useQuery<{ count: number }>({
    queryKey: ["notifications", "unread-count"],
    queryFn: () => api.get("/notifications/unread-count"),
    enabled,
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
  });
}

export function useMarkRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (notificationIds: string[]) =>
      api.post("/notifications/read", { notification_ids: notificationIds }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

export function useMarkAllRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post("/notifications/read-all"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

export function useDeleteNotifications() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (notificationIds: string[]) =>
      api.post("/notifications/delete", { notification_ids: notificationIds }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}
