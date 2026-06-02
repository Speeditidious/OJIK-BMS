import { useCallback, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

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

function prefsQueryKey(userId: string | null | undefined) {
  return ["user-preferences", userId ?? null] as const;
}

export function useScoreUpdatesPrefs(): ScoreUpdatesNewPlayPrefs {
  const { isInitialized, user } = useAuthStore();
  const { data } = useQuery({
    queryKey: prefsQueryKey(user?.id),
    queryFn: () => api.get<{ preferences: Record<string, boolean> }>("/users/me/preferences"),
    staleTime: 10 * 60 * 1000,
    enabled: isInitialized && !!user,
  });
  return { ...DEFAULT_PREFS, ...(data?.preferences ?? {}) } as ScoreUpdatesNewPlayPrefs;
}

export function useUpdateScoreUpdatesPrefs() {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const key = prefsQueryKey(user?.id);
  return useMutation({
    mutationFn: (preferences: Partial<ScoreUpdatesNewPlayPrefs>) =>
      api.patch<{ preferences: Record<string, boolean> }>("/users/me/preferences", { preferences }),
    onMutate: async (newPrefs) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<{ preferences: Record<string, boolean> }>(key);
      queryClient.setQueryData(key, (old: { preferences: Record<string, boolean> } | undefined) => ({
        preferences: { ...(old?.preferences ?? {}), ...newPrefs },
      }));
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous !== undefined) {
        queryClient.setQueryData(key, context.previous);
      }
    },
    onSuccess: (data) => {
      queryClient.setQueryData(key, data);
    },
  });
}

// ---------------------------------------------------------------------------
// Clear type visibility preferences
// ---------------------------------------------------------------------------

/** Clear types that can be hidden (MAX=9 … ASSIST=2). FAILED(1) and NO PLAY(0) are always shown. */
export const HIDEABLE_CLEAR_TYPES = [9, 8, 7, 6, 5, 4, 3, 2] as const;

/** Clear types not present in LR2. Excluded from the LR2 bucket UI. */
export const LR2_MISSING_CLEAR_TYPES: ReadonlySet<number> = new Set([2, 6]);

export type ClientVisibilityKey = "all" | "lr2" | "beatoraja";
export type VisibilityMap = Record<string, boolean>;
export type ClearTypeVisibilityMode = "global" | "per_client";

export interface ClearTypeVisibilityPrefs {
  mode: ClearTypeVisibilityMode;
  global: VisibilityMap;
  all: VisibilityMap;
  lr2: VisibilityMap;
  beatoraja: VisibilityMap;
}

const EMPTY_VISIBILITY_PREFS: ClearTypeVisibilityPrefs = {
  mode: "global",
  global: {},
  all: {},
  lr2: {},
  beatoraja: {},
};

export function normalizeClearTypeVisibility(raw: unknown): ClearTypeVisibilityPrefs {
  if (!raw || typeof raw !== "object") return { ...EMPTY_VISIBILITY_PREFS };
  const obj = raw as Record<string, unknown>;

  // Old flat format: all values are boolean → treat as legacy single-set visibility
  const isLegacy =
    !("mode" in obj) &&
    Object.values(obj).every((v) => typeof v === "boolean");
  if (isLegacy) {
    const legacy = obj as VisibilityMap;
    return {
      mode: "global",
      global: { ...legacy },
      all: {},
      lr2: {},
      beatoraja: {},
    };
  }

  const mode: ClearTypeVisibilityMode = obj.mode === "per_client" ? "per_client" : "global";
  const pick = (k: string): VisibilityMap => {
    const v = obj[k];
    return v && typeof v === "object" ? (v as VisibilityMap) : {};
  };
  return {
    mode,
    global: pick("global"),
    all: pick("all"),
    lr2: pick("lr2"),
    beatoraja: pick("beatoraja"),
  };
}

export function useClearTypeVisibility(
  clientKey: ClientVisibilityKey = "all",
  enabled = true,
): {
  prefs: ClearTypeVisibilityPrefs;
  hiddenTypes: Set<number>;
  visibility: VisibilityMap;
  isHidden: (ct: number) => boolean;
  getDisplayClearType: (ct: number) => number;
  isLoading: boolean;
} {
  const { isInitialized, user } = useAuthStore();
  const { data, isLoading } = useQuery({
    queryKey: prefsQueryKey(user?.id),
    queryFn: () => api.get<{ preferences: Record<string, unknown> }>("/users/me/preferences"),
    staleTime: 10 * 60 * 1000,
    enabled: enabled && isInitialized && !!user,
  });

  const prefs = useMemo(
    () => normalizeClearTypeVisibility(data?.preferences?.clear_type_visibility),
    [data],
  );

  const visibility = useMemo<VisibilityMap>(
    () => (prefs.mode === "global" ? prefs.global : prefs[clientKey]) ?? {},
    [prefs, clientKey],
  );

  const hiddenTypes = useMemo(() => {
    const set = new Set<number>();
    for (const [key, value] of Object.entries(visibility)) {
      if (value === false) set.add(Number(key));
    }
    return set;
  }, [visibility]);

  const isHidden = useCallback((ct: number) => hiddenTypes.has(ct), [hiddenTypes]);

  const getDisplayClearType = useCallback(
    (ct: number) => {
      let result = ct;
      while (result > 1 && hiddenTypes.has(result)) {
        result--;
      }
      return result;
    },
    [hiddenTypes],
  );

  return { prefs, hiddenTypes, visibility, isHidden, getDisplayClearType, isLoading };
}

export function useUserClearTypeVisibility(
  targetUserId: string,
  clientKey: ClientVisibilityKey = "all",
  enabled = true,
): {
  prefs: ClearTypeVisibilityPrefs;
  hiddenTypes: Set<number>;
  visibility: VisibilityMap;
  isHidden: (ct: number) => boolean;
  getDisplayClearType: (ct: number) => number;
  isLoading: boolean;
} {
  const { data, isLoading } = useQuery({
    queryKey: ["user-clear-visibility", targetUserId],
    queryFn: () =>
      api.get<{ clear_type_visibility: unknown }>(
        `/users/by-id/${targetUserId}/preferences/clear-visibility`,
      ),
    staleTime: 10 * 60 * 1000,
    enabled: enabled && !!targetUserId,
  });

  const prefs = useMemo(
    () => normalizeClearTypeVisibility(data?.clear_type_visibility),
    [data],
  );

  const visibility = useMemo<VisibilityMap>(
    () => (prefs.mode === "global" ? prefs.global : prefs[clientKey]) ?? {},
    [prefs, clientKey],
  );

  const hiddenTypes = useMemo(() => {
    const set = new Set<number>();
    for (const [k, v] of Object.entries(visibility)) {
      if (v === false) set.add(Number(k));
    }
    return set;
  }, [visibility]);

  const isHidden = useCallback((ct: number) => hiddenTypes.has(ct), [hiddenTypes]);

  const getDisplayClearType = useCallback(
    (ct: number) => {
      let result = ct;
      while (result > 1 && hiddenTypes.has(result)) result--;
      return result;
    },
    [hiddenTypes],
  );

  return { prefs, hiddenTypes, visibility, isHidden, getDisplayClearType, isLoading };
}

export function useUpdateClearTypeVisibility() {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const key = prefsQueryKey(user?.id);
  return useMutation({
    mutationFn: (nextPrefs: ClearTypeVisibilityPrefs) =>
      api.patch<{ preferences: Record<string, unknown> }>("/users/me/preferences", {
        preferences: { clear_type_visibility: nextPrefs },
      }),
    onMutate: async (nextPrefs) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<{ preferences: Record<string, unknown> }>(key);
      queryClient.setQueryData(key, (old: { preferences: Record<string, unknown> } | undefined) => ({
        preferences: { ...(old?.preferences ?? {}), clear_type_visibility: nextPrefs },
      }));
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous !== undefined) {
        queryClient.setQueryData(key, context.previous);
      }
    },
    onSuccess: (data) => {
      queryClient.setQueryData(key, data);
    },
  });
}

// ---------------------------------------------------------------------------
// Level display preferences
// ---------------------------------------------------------------------------

export interface LevelDisplayPrefs {
  favorite: boolean;
  server_default: boolean;
  user_added: boolean;
  ojik_custom: boolean;
  favorite_show_non_regular: boolean;
  server_default_show_non_regular: boolean;
  user_added_show_non_regular: boolean;
  ojik_custom_show_non_regular: boolean;
}

export const DEFAULT_LEVEL_DISPLAY_PREFS: LevelDisplayPrefs = {
  favorite: true,
  server_default: false,
  user_added: false,
  ojik_custom: false,
  favorite_show_non_regular: true,
  server_default_show_non_regular: true,
  user_added_show_non_regular: true,
  ojik_custom_show_non_regular: true,
};

export function normalizeLevelDisplayPrefs(raw: unknown): LevelDisplayPrefs {
  const obj = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  return {
    favorite: typeof obj.favorite === "boolean" ? obj.favorite : true,
    server_default: typeof obj.server_default === "boolean" ? obj.server_default : false,
    user_added: typeof obj.user_added === "boolean" ? obj.user_added : false,
    ojik_custom: typeof obj.ojik_custom === "boolean" ? obj.ojik_custom : false,
    favorite_show_non_regular:
      typeof obj.favorite_show_non_regular === "boolean" ? obj.favorite_show_non_regular : true,
    server_default_show_non_regular:
      typeof obj.server_default_show_non_regular === "boolean"
        ? obj.server_default_show_non_regular
        : true,
    user_added_show_non_regular:
      typeof obj.user_added_show_non_regular === "boolean" ? obj.user_added_show_non_regular : true,
    ojik_custom_show_non_regular:
      typeof obj.ojik_custom_show_non_regular === "boolean"
        ? obj.ojik_custom_show_non_regular
        : true,
  };
}

export function useLevelDisplayPrefs(): LevelDisplayPrefs {
  const { isInitialized, user } = useAuthStore();
  const { data } = useQuery({
    queryKey: prefsQueryKey(user?.id),
    queryFn: () => api.get<{ preferences: Record<string, unknown> }>("/users/me/preferences"),
    staleTime: 10 * 60 * 1000,
    enabled: isInitialized && !!user,
  });
  return normalizeLevelDisplayPrefs(data?.preferences?.level_display);
}

export function useUpdateLevelDisplayPrefs() {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const key = prefsQueryKey(user?.id);
  return useMutation({
    mutationFn: (nextPrefs: LevelDisplayPrefs) =>
      api.patch<{ preferences: Record<string, unknown> }>("/users/me/preferences", {
        preferences: { level_display: nextPrefs },
      }),
    onMutate: async (nextPrefs) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<{ preferences: Record<string, unknown> }>(key);
      queryClient.setQueryData(key, (old: { preferences: Record<string, unknown> } | undefined) => ({
        preferences: { ...(old?.preferences ?? {}), level_display: nextPrefs },
      }));
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous !== undefined) queryClient.setQueryData(key, context.previous);
    },
    onSuccess: (data) => {
      queryClient.setQueryData(key, data);
    },
  });
}
