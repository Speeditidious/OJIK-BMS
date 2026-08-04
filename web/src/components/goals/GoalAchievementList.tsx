"use client";

import { useTranslation } from "react-i18next";
import { GoalCard } from "@/components/goals/GoalCard";
import { useGoalAchievements } from "@/hooks/use-goals";

interface GoalAchievementListProps {
  /** Whose day is being viewed. Omit for the signed-in user's own dashboard. */
  userId?: string;
  /** YYYY-MM-DD. */
  date?: string;
}

/**
 * Goals achieved on a given day, rendered above the course records in the
 * update-detail and all-records tabs. Renders nothing when the day has no
 * achievements.
 */
export function GoalAchievementList({ userId, date }: GoalAchievementListProps) {
  const { t } = useTranslation();
  const { data } = useGoalAchievements(date ?? null, userId);
  const goals = data?.goals ?? [];

  if (goals.length === 0) return null;

  // Same frame as SectionTable / CourseSectionTable so the goal block reads as
  // one more section of the record detail, with the goal-tab card inside.
  return (
    <div className="border border-border/40 rounded-lg overflow-hidden">
      <div className="px-3 py-2 bg-muted/30 border-b border-border/40">
        <p className="text-body font-semibold text-foreground">
          {t("dashboard.daySheet.goalsAchieved")}{" "}
          <span className="text-muted-foreground font-normal text-label">({goals.length})</span>
        </p>
      </div>
      <div className="space-y-2 p-3">
        {goals.map((goal) => (
          <GoalCard key={goal.goal_id} goal={goal} canDelete={false} />
        ))}
      </div>
    </div>
  );
}
