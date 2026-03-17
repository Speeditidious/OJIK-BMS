import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface Schedule {
  id: string;
  title: string;
  description: string | null;
  scheduled_date: string | null;
  scheduled_time: string | null;
  is_completed: boolean;
}

export function useSchedules(targetDate?: string) {
  const params = targetDate ? `?target_date=${targetDate}` : "";
  return useQuery({
    queryKey: ["schedules", targetDate],
    queryFn: () => api.get<{ schedules: Schedule[] }>(`/schedules/${params}`),
  });
}

export function useCreateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; description?: string; scheduled_date?: string }) =>
      api.post<Schedule>("/schedules/", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });
}

export function useUpdateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id: string;
      title?: string;
      description?: string;
      scheduled_date?: string;
      is_completed?: boolean;
    }) => api.patch<Schedule>(`/schedules/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });
}

export function useDeleteSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/schedules/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });
}
