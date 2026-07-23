"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  CLEAR_TYPE_LABELS,
  LR2_CLEAR_TYPE_LABELS,
  BEATORAJA_CLEAR_TYPE_LABELS,
} from "@/components/charts/ClearDistributionChart";
import type { GoalRecord } from "@/hooks/use-goals";
import { useDeleteGoal } from "@/hooks/use-goals";
import { formatRatePercent } from "@/lib/rate-format";
import { formatTableLevelWithSymbolForDisplay } from "@/lib/table-level-display";
import { songHref } from "@/lib/song-href";

function clearLabel(clientType: string, clearType: number): string {
  const labels =
    clientType === "lr2" ? LR2_CLEAR_TYPE_LABELS : clientType === "beatoraja" ? BEATORAJA_CLEAR_TYPE_LABELS : CLEAR_TYPE_LABELS;
  return labels[clearType] ?? CLEAR_TYPE_LABELS[clearType] ?? String(clearType);
}

interface GoalCardProps {
  goal: GoalRecord;
}

export function GoalCard({ goal }: GoalCardProps) {
  const { t } = useTranslation();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const deleteGoal = useDeleteGoal();

  const title = goal.goal_type === "chart" ? goal.title : goal.course_name;
  const href =
    goal.goal_type === "chart" && (goal.fumen_sha256 || goal.fumen_md5)
      ? songHref({ sha256: goal.fumen_sha256, md5: goal.fumen_md5 })
      : null;
  const levelDisplay =
    goal.goal_type === "chart" && goal.level
      ? formatTableLevelWithSymbolForDisplay({ tableSymbol: undefined, level: goal.level })
      : null;

  const metrics: string[] = [];
  if (goal.target_clear_type != null) metrics.push(clearLabel(goal.client_type, goal.target_clear_type));
  if (goal.target_min_bp != null) metrics.push(`BP ${goal.target_min_bp}`);
  if (goal.target_rank != null) metrics.push(goal.target_rank);
  if (goal.target_rate != null) metrics.push(formatRatePercent(goal.target_rate));

  function handleDelete() {
    deleteGoal.mutate(goal.goal_id, { onSuccess: () => setConfirmOpen(false) });
  }

  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-border bg-card/60 px-4 py-3">
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-border/60 bg-secondary/50 px-2 py-0.5 text-caption font-medium uppercase text-muted-foreground">
            {goal.client_type}
          </span>
          {levelDisplay && (
            <span className="rounded-md border border-primary/40 bg-primary/10 px-1.5 py-0.5 text-caption font-semibold text-primary">
              {levelDisplay}
            </span>
          )}
          {goal.goal_type === "course" && goal.dan_title && (
            <span className="rounded-md border border-accent/40 bg-accent/10 px-1.5 py-0.5 text-caption font-semibold text-accent">
              {goal.dan_title}
            </span>
          )}
          {href ? (
            <a href={href} className="truncate text-body font-semibold hover:text-primary">
              {title}
            </a>
          ) : (
            <span className="truncate text-body font-semibold">{title}</span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {metrics.map((m, i) => (
            <span key={i} className="rounded-md bg-secondary/60 px-2 py-0.5 text-caption font-medium">
              {m}
            </span>
          ))}
          {metrics.length === 0 && (
            <span className="text-caption text-muted-foreground">{t("goals.card.noMetrics")}</span>
          )}
        </div>
        {goal.comment && <p className="truncate text-caption text-muted-foreground">{goal.comment}</p>}
        {goal.status === "achieved" && goal.achieved_recorded_at && (
          <p className="text-caption text-muted-foreground">
            {t("goals.card.achievedOn", { date: goal.achieved_recorded_at.slice(0, 10) })}
          </p>
        )}
      </div>

      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 text-muted-foreground hover:text-destructive"
        aria-label={t("goals.card.deleteAria")}
        onClick={() => setConfirmOpen(true)}
      >
        <Trash2 className="h-4 w-4" />
      </Button>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{t("goals.card.deleteConfirmTitle")}</DialogTitle>
          </DialogHeader>
          <p className="text-body text-muted-foreground">{t("goals.card.deleteConfirmBody")}</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)} disabled={deleteGoal.isPending}>
              {t("common.actions.cancel")}
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteGoal.isPending} className="gap-2">
              {deleteGoal.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              {t("common.actions.delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
