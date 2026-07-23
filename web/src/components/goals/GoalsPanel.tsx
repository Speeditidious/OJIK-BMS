"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useGoals } from "@/hooks/use-goals";
import { GoalCard } from "@/components/goals/GoalCard";
import { GoalSetupDialog } from "@/components/goals/GoalSetupDialog";

interface GoalsPanelProps {
  isOwner: boolean;
}

/**
 * Active/achieved goal lists next to the user's activity calendar (plan
 * §3.5). Goals are always self-scoped server-side (see goals.py), so this
 * panel only renders anything meaningful when `isOwner`.
 */
export function GoalsPanel({ isOwner }: GoalsPanelProps) {
  const { t } = useTranslation();
  const [setupOpen, setSetupOpen] = useState(false);
  const activeGoals = useGoals("active", isOwner);
  const achievedGoals = useGoals("achieved", isOwner);

  if (!isOwner) return null;

  return (
    <Card>
      <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 space-y-1.5">
          <CardTitle>{t("goals.panel.title")}</CardTitle>
          <CardDescription>{t("goals.panel.description")}</CardDescription>
        </div>
        <Button size="lg" onClick={() => setSetupOpen(true)} className="gap-2 shadow-sm">
          <Plus className="h-4 w-4" />
          <span className="font-semibold">{t("goals.panel.setGoal")}</span>
        </Button>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="active">
          <TabsList>
            <TabsTrigger value="active">
              {t("goals.panel.activeTab", { count: activeGoals.data?.goals.length ?? 0 })}
            </TabsTrigger>
            <TabsTrigger value="achieved">
              {t("goals.panel.achievedTab", { count: achievedGoals.data?.goals.length ?? 0 })}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="active" className="space-y-2">
            {activeGoals.isLoading ? (
              <p className="text-body text-muted-foreground">{t("common.states.loading")}</p>
            ) : activeGoals.data?.goals.length ? (
              activeGoals.data.goals.map((goal) => <GoalCard key={goal.goal_id} goal={goal} />)
            ) : (
              <p className="text-body text-muted-foreground">{t("goals.panel.noActiveGoals")}</p>
            )}
          </TabsContent>

          <TabsContent value="achieved" className="space-y-2">
            {achievedGoals.isLoading ? (
              <p className="text-body text-muted-foreground">{t("common.states.loading")}</p>
            ) : achievedGoals.data?.goals.length ? (
              achievedGoals.data.goals.map((goal) => <GoalCard key={goal.goal_id} goal={goal} />)
            ) : (
              <p className="text-body text-muted-foreground">{t("goals.panel.noAchievedGoals")}</p>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>

      <GoalSetupDialog open={setupOpen} onClose={() => setSetupOpen(false)} />
    </Card>
  );
}
