"use client";

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Plus } from "lucide-react";
import { verticalListSortingStrategy } from "@dnd-kit/sortable";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useGoals } from "@/hooks/use-goals";
import { GoalCard } from "@/components/goals/GoalCard";
import { GoalFilterBar } from "@/components/goals/GoalFilterBar";
import { GoalSetupDialog } from "@/components/goals/GoalSetupDialog";
import { SortableGoalList } from "@/components/goals/SortableGoalList";
import type { GoalFilter } from "@/lib/goal-filter-core";
import { applyLevelDisplayPreference, emptyGoalFilter, filterGoals } from "@/lib/goal-filter-core";

interface GoalsPanelProps {
  /** Whose goals to show. Omit for the signed-in user's own dashboard. */
  userId?: string;
  isOwner: boolean;
}

/**
 * Active/achieved goal lists next to the user's activity calendar. Readable on
 * any player's dashboard; only the owner sees the create/delete affordances.
 */
export function GoalsPanel({ userId, isOwner }: GoalsPanelProps) {
  const { t } = useTranslation();
  const [setupOpen, setSetupOpen] = useState(false);
  // Each tab keeps its own filter — the achieved tab has an extra date
  // dimension, and carrying a lamp selection across tabs surprises users.
  const [activeFilter, setActiveFilter] = useState<GoalFilter>(emptyGoalFilter);
  const [achievedFilter, setAchievedFilter] = useState<GoalFilter>(emptyGoalFilter);

  const activeGoals = useGoals("active", userId);
  const achievedGoals = useGoals("achieved", userId);

  const activeList = useMemo(() => activeGoals.data?.goals ?? [], [activeGoals.data]);
  const achievedList = useMemo(() => achievedGoals.data?.goals ?? [], [achievedGoals.data]);
  const activeTables = activeGoals.data?.tables ?? [];
  const achievedTables = achievedGoals.data?.tables ?? [];
  const preferenceActiveList = useMemo(
    () => applyLevelDisplayPreference(activeList, activeTables, activeFilter.applyLevelDisplayPrefs),
    [activeList, activeTables, activeFilter.applyLevelDisplayPrefs],
  );
  const preferenceAchievedList = useMemo(
    () => applyLevelDisplayPreference(
      achievedList,
      achievedTables,
      achievedFilter.applyLevelDisplayPrefs,
    ),
    [achievedList, achievedTables, achievedFilter.applyLevelDisplayPrefs],
  );
  const filteredActive = useMemo(
    () => filterGoals(preferenceActiveList, activeFilter),
    [preferenceActiveList, activeFilter],
  );
  const filteredAchieved = useMemo(
    () => filterGoals(preferenceAchievedList, achievedFilter),
    [preferenceAchievedList, achievedFilter],
  );

  return (
    <Card>
      <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 space-y-1.5">
          <CardTitle>{isOwner ? t("goals.panel.title") : t("goals.panel.othersTitle")}</CardTitle>
          <CardDescription>
            {isOwner ? t("goals.panel.description") : t("goals.panel.othersDescription")}
          </CardDescription>
        </div>
        {isOwner && (
          <Button size="lg" onClick={() => setSetupOpen(true)} className="gap-2 shadow-sm">
            <Plus className="h-4 w-4" />
            <span className="font-semibold">{t("goals.panel.setGoal")}</span>
          </Button>
        )}
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="active">
          <TabsList>
            <TabsTrigger value="active">
              {t("goals.panel.activeTab", { count: activeList.length })}
            </TabsTrigger>
            <TabsTrigger value="achieved">
              {t("goals.panel.achievedTab", { count: achievedList.length })}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="active" className="space-y-3">
            {activeGoals.isLoading ? (
              <p className="text-body text-muted-foreground">{t("common.states.loading")}</p>
            ) : activeList.length === 0 ? (
              <p className="text-body text-muted-foreground">{t("goals.panel.noActiveGoals")}</p>
            ) : (
              <>
                <GoalFilterBar
                  goals={preferenceActiveList}
                  tables={activeTables}
                  filter={activeFilter}
                  onFilterChange={setActiveFilter}
                  showAchievedRange={false}
                />
                {filteredActive.length === 0 ? (
                  <p className="text-body text-muted-foreground">{t("goals.filter.noMatch")}</p>
                ) : (
                  <SortableGoalList
                    goals={filteredActive}
                    strategy={verticalListSortingStrategy}
                    // Reordering a partial view would move goals the user
                    // cannot see, so it is blocked while anything is filtered out.
                    disabled={!isOwner || filteredActive.length !== preferenceActiveList.length}
                    disabledReason={isOwner ? t("goals.card.reorderDisabledByFilter") : undefined}
                    className="space-y-2"
                    renderItem={(goal, dragHandle) => (
                      <GoalCard goal={goal} canDelete={isOwner} dragHandle={dragHandle} />
                    )}
                  />
                )}
              </>
            )}
          </TabsContent>

          <TabsContent value="achieved" className="space-y-3">
            {achievedGoals.isLoading ? (
              <p className="text-body text-muted-foreground">{t("common.states.loading")}</p>
            ) : achievedList.length === 0 ? (
              <p className="text-body text-muted-foreground">{t("goals.panel.noAchievedGoals")}</p>
            ) : (
              <>
                <GoalFilterBar
                  goals={preferenceAchievedList}
                  tables={achievedTables}
                  filter={achievedFilter}
                  onFilterChange={setAchievedFilter}
                  showAchievedRange
                />
                {filteredAchieved.length === 0 ? (
                  <p className="text-body text-muted-foreground">{t("goals.filter.noMatch")}</p>
                ) : (
                  <div className="space-y-2">
                    {filteredAchieved.map((goal) => (
                      <GoalCard key={goal.goal_id} goal={goal} canDelete={isOwner} />
                    ))}
                  </div>
                )}
              </>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>

      {isOwner && <GoalSetupDialog open={setupOpen} onClose={() => setSetupOpen(false)} />}
    </Card>
  );
}
