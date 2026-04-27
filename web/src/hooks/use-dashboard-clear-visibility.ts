import { useClearTypeVisibility, useUserClearTypeVisibility, type ClientVisibilityKey } from "./use-preferences";
import { useAuthStore } from "@/stores/auth";

export type ClearVisibilitySource = "target" | "viewer";

export function useDashboardClearVisibility(
  targetUserId: string,
  clientKey: ClientVisibilityKey,
  source: ClearVisibilitySource,
  isOwner: boolean,
) {
  const { user, isInitialized } = useAuthStore();

  // Owner always uses their own prefs. Visitor with cv=mine uses viewer prefs.
  // Effective source falls back to target when viewer is not logged in.
  const effectiveSource: ClearVisibilitySource =
    isOwner || (source === "viewer" && !!user) ? "viewer" : "target";

  const viewer = useClearTypeVisibility(
    clientKey,
    isInitialized && effectiveSource === "viewer",
  );
  const target = useUserClearTypeVisibility(
    targetUserId,
    clientKey,
    isInitialized && effectiveSource === "target",
  );

  if (effectiveSource === "viewer") {
    return { ...viewer, isLoading: !isInitialized || viewer.isLoading, source: "viewer" as const };
  }
  return { ...target, isLoading: !isInitialized || target.isLoading, source: "target" as const };
}
