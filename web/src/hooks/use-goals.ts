import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface GoalRecord {
  goal_id: string;
  goal_type: "chart" | "course";
  client_type: string;
  table_slug: string | null;
  fumen_sha256: string | null;
  fumen_md5: string | null;
  course_id: string | null;
  target_clear_type: number | null;
  target_min_bp: number | null;
  target_rank: string | null;
  target_rate: number | null;
  projected_rating: number | null;
  comment: string | null;
  status: "active" | "achieved";
  created_at: string | null;
  achieved_at: string | null;
  achieved_recorded_at: string | null;
  baseline_snapshot: {
    clear_type: number | null;
    min_bp: number | null;
    rank: string | null;
    rate: number | null;
  };
  title: string | null;
  artist: string | null;
  level: string | null;
  course_name: string | null;
  dan_title: string | null;
}

export interface GoalListResponse {
  goals: GoalRecord[];
  default_client_type: string | null;
}

/** Active or achieved goals for the current user (goals are always self-scoped — see goals.py). */
export function useGoals(status: "active" | "achieved", enabled: boolean = true) {
  return useQuery<GoalListResponse>({
    queryKey: ["goals", status],
    queryFn: () => api.get<GoalListResponse>(`/goals/?status=${status}`),
    enabled,
    staleTime: 30 * 1000,
  });
}

export interface GoalCreatePayload {
  goal_type: "chart" | "course";
  client_type: string;
  table_slug?: string | null;
  fumen_sha256?: string | null;
  fumen_md5?: string | null;
  course_id?: string | null;
  target_clear_type?: number | null;
  target_min_bp?: number | null;
  target_rank?: string | null;
  target_rate?: number | null;
  comment?: string | null;
}

export function useCreateGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: GoalCreatePayload) => api.post<GoalRecord>("/goals/", payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals", "active"] });
    },
  });
}

export function useDeleteGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (goalId: string) => api.delete(`/goals/${goalId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals", "active"] });
      queryClient.invalidateQueries({ queryKey: ["goals", "achieved"] });
    },
  });
}

/** Goals achieved on a given calendar date (DayStatSheet's achievement section). */
export function useGoalAchievements(date: string | null, enabled: boolean = true) {
  return useQuery<{ goals: GoalRecord[] }>({
    queryKey: ["goal-achievements", date],
    queryFn: () => api.get<{ goals: GoalRecord[] }>(`/goals/achievements?date=${date}`),
    enabled: enabled && !!date,
    staleTime: 60 * 1000,
  });
}

export interface TargetCourse {
  course_id: string;
  name: string;
  dan_title: string | null;
  is_recognized: boolean;
  table_slug: string | null;
  chart_count: number;
}

/** Active courses available as goal targets, split into recognized (dan) / unrecognized in the UI. */
export function useTargetCourses(enabled: boolean = true) {
  return useQuery<{ courses: TargetCourse[] }>({
    queryKey: ["goal-target-courses"],
    queryFn: () => api.get<{ courses: TargetCourse[] }>("/goals/target-courses"),
    enabled,
    staleTime: 5 * 60 * 1000,
  });
}

export interface GoalBaseline {
  clear_type: number | null;
  min_bp: number | null;
  rank: string | null;
  rate: number | null;
}

interface GoalBaselineParams {
  goalType: "chart" | "course";
  clientType: string | null;
  fumenSha256?: string | null;
  fumenMd5?: string | null;
  courseId?: string | null;
  enabled?: boolean;
}

/** Live baseline preview for the goal-setup dialog's frontend validation (authoritative check happens again on POST). */
export function useGoalBaseline({
  goalType,
  clientType,
  fumenSha256,
  fumenMd5,
  courseId,
  enabled = true,
}: GoalBaselineParams) {
  return useQuery<GoalBaseline>({
    queryKey: ["goal-baseline", goalType, clientType, fumenSha256 ?? null, fumenMd5 ?? null, courseId ?? null],
    queryFn: () => {
      const params = new URLSearchParams({ goal_type: goalType, client_type: clientType! });
      if (goalType === "chart") {
        if (fumenSha256) params.set("fumen_sha256", fumenSha256);
        if (fumenMd5) params.set("fumen_md5", fumenMd5);
      } else if (courseId) {
        params.set("course_id", courseId);
      }
      return api.get<GoalBaseline>(`/goals/baseline?${params.toString()}`);
    },
    enabled:
      enabled &&
      !!clientType &&
      (goalType === "chart" ? !!(fumenSha256 || fumenMd5) : !!courseId),
    staleTime: 10 * 1000,
  });
}
