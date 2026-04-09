import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface ScoreUpdatesNewPlayPrefs {
  score_updates_lamp_include_new_plays: boolean;
  score_updates_score_include_new_plays: boolean;
  score_updates_bp_include_new_plays: boolean;
  score_updates_combo_include_new_plays: boolean;
}

const DEFAULT_PREFS: ScoreUpdatesNewPlayPrefs = {
  score_updates_lamp_include_new_plays: true,
  score_updates_score_include_new_plays: true,
  score_updates_bp_include_new_plays: true,
  score_updates_combo_include_new_plays: true,
};

const QUERY_KEY = ["user-preferences"];

export function useScoreUpdatesPrefs(): ScoreUpdatesNewPlayPrefs {
  const { data } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => api.get<{ preferences: Record<string, boolean> }>("/users/me/preferences"),
    staleTime: 10 * 60 * 1000,
  });
  return { ...DEFAULT_PREFS, ...(data?.preferences ?? {}) } as ScoreUpdatesNewPlayPrefs;
}

export function useUpdateScoreUpdatesPrefs() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (preferences: Partial<ScoreUpdatesNewPlayPrefs>) =>
      api.patch<{ preferences: Record<string, boolean> }>("/users/me/preferences", { preferences }),
    onMutate: async (newPrefs) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEY });
      const previous = queryClient.getQueryData<{ preferences: Record<string, boolean> }>(QUERY_KEY);
      queryClient.setQueryData(QUERY_KEY, (old: { preferences: Record<string, boolean> } | undefined) => ({
        preferences: { ...(old?.preferences ?? {}), ...newPrefs },
      }));
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous !== undefined) {
        queryClient.setQueryData(QUERY_KEY, context.previous);
      }
    },
    onSuccess: (data) => {
      queryClient.setQueryData(QUERY_KEY, data);
    },
  });
}
