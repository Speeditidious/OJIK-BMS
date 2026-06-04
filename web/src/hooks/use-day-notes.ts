import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface DayNoteSummary {
  date: string;
  updated_at: string;
}

export interface DayNote {
  date: string;
  title: string | null;
  content: string;
  created_at: string;
  updated_at: string;
}

/** Month note summaries (dates only, no content) — used for cell icon display. */
export function useMonthDayNotes(userId: string | null, year: number, month: number) {
  return useQuery<DayNoteSummary[]>({
    queryKey: ["day-notes", userId, year, month],
    queryFn: () => api.get(`/users/${userId}/day-notes?year=${year}&month=${month}`),
    enabled: !!userId,
    staleTime: 2 * 60 * 1000,
  });
}

/** Single note with content — lazy fetched when popover/detail opens. */
export function useDayNote(userId: string | null, date: string | null) {
  return useQuery<DayNote | null>({
    queryKey: ["day-note", userId, date],
    queryFn: () => api.get(`/users/${userId}/day-notes/${date}`),
    enabled: !!userId && !!date,
    staleTime: 2 * 60 * 1000,
  });
}

export function useUpsertDayNote(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ date, title, content }: { date: string; title?: string | null; content: string }) =>
      api.put(`/me/day-notes/${date}`, { title: title ?? null, content }),
    onSuccess: (data, { date }: { date: string; title?: string | null; content: string }) => {
      const [year, month] = date.split("-").map(Number);
      queryClient.invalidateQueries({ queryKey: ["day-note", userId, date] });
      queryClient.invalidateQueries({ queryKey: ["day-notes", userId, year, month] });
      // Optimistic: update single note cache immediately
      if (data) {
        queryClient.setQueryData(["day-note", userId, date], data);
      }
    },
  });
}

export function useDeleteDayNote(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (date: string) => api.delete(`/me/day-notes/${date}`),
    onSuccess: (_data, date) => {
      const [year, month] = date.split("-").map(Number);
      queryClient.setQueryData(["day-note", userId, date], null);
      queryClient.invalidateQueries({ queryKey: ["day-notes", userId, year, month] });
    },
  });
}
