"use client";

import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { ArrowRight, ArrowUpRight, UserCircle } from "lucide-react";
import { rectSortingStrategy } from "@dnd-kit/sortable";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { AvatarImage } from "@/components/common/AvatarImage";
import { GoalCard } from "@/components/goals/GoalCard";
import { SortableGoalList } from "@/components/goals/SortableGoalList";
import { useGoals } from "@/hooks/use-goals";
import { resolveAvatarUrl } from "@/lib/avatar";
import { applyLevelDisplayPreference } from "@/lib/goal-filter-core";
import { formatJoinDate, timeAgo } from "@/lib/time";

interface DashboardUserHeaderProps {
  username: string;
  avatarUrl: string | null;
  userId: string;
  createdAt: string;
  lastSyncedAt: string | null;
  isOwner?: boolean;
  /** Jump to the dashboard's goals tab. Omit to hide the shortcut icon. */
  onGoToGoals?: () => void;
}

export function DashboardUserHeader({
  username,
  avatarUrl,
  userId,
  createdAt,
  lastSyncedAt,
  isOwner = false,
  onGoToGoals,
}: DashboardUserHeaderProps) {
  const { t } = useTranslation();
  const activeGoals = useGoals("active", undefined, isOwner);
  const totalActiveCount = activeGoals.data?.goals.length ?? 0;
  const visibleGoals = useMemo(
    () =>
      applyLevelDisplayPreference(
        activeGoals.data?.goals ?? [],
        activeGoals.data?.tables ?? [],
        true,
      ),
    [activeGoals.data],
  );

  return (
    <section className="rounded-xl border border-border bg-card/70 p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
        {avatarUrl ? (
          <AvatarImage
            src={resolveAvatarUrl(avatarUrl)}
            alt=""
            size={64}
            fallbackText={username}
            className="rounded-full object-cover ring-2 ring-primary/30"
          />
        ) : (
          <div
            aria-hidden="true"
            className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/20 text-2xl font-bold text-primary ring-2 ring-primary/30"
          >
            {username.charAt(0).toUpperCase()}
          </div>
        )}

        <div className="min-w-0 flex-1 space-y-1">
          <h1 className="text-2xl font-bold">{username}</h1>
          <p className="text-body text-muted-foreground">{t("profile.info.joinedAt", { date: formatJoinDate(createdAt, t) })}</p>
          <p className="text-body text-muted-foreground">
            {lastSyncedAt
              ? t("dashboard.header.syncedAt", { time: timeAgo(lastSyncedAt, t) })
              : t("dashboard.header.loading")}
          </p>
        </div>

        <Button asChild size="lg" className="w-full gap-2 shadow-sm sm:w-auto sm:shrink-0">
          <a href={`/users/${userId}`}>
            <UserCircle className="h-5 w-5" />
            <span className="font-semibold">{t("profile.info.viewProfile")}</span>
            <ArrowRight className="h-4 w-4" />
          </a>
        </Button>
      </div>

      {isOwner && (activeGoals.isLoading || visibleGoals.length > 0) && (
        <div className="mt-4 border-t border-border/70 pt-4">
          <div className="mb-2 flex items-center gap-1.5">
            <span className="text-body font-medium">
              {t("goals.panel.setGoalsCount", { count: totalActiveCount })}
            </span>
            {onGoToGoals && (
              <TooltipProvider delayDuration={150}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      onClick={onGoToGoals}
                      className="text-muted-foreground transition-colors hover:text-foreground"
                      aria-label={t("goals.panel.goToGoalsTab")}
                    >
                      <ArrowUpRight className="h-4 w-4" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent className="text-label">
                    {t("goals.panel.goToGoalsTab")}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>
          {activeGoals.isLoading ? (
            <div className="grid gap-2 lg:grid-cols-3">
              {Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="h-16 animate-pulse rounded-lg bg-muted" />
              ))}
            </div>
          ) : (
            <SortableGoalList
              goals={visibleGoals}
              strategy={rectSortingStrategy}
              disabled={visibleGoals.length !== totalActiveCount}
              className="grid gap-2 lg:grid-cols-3"
              renderItem={(goal, dragHandle) => (
                <GoalCard goal={goal} compact dragHandle={dragHandle} />
              )}
            />
          )}
        </div>
      )}
    </section>
  );
}
