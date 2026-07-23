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
import type { TableLevelRef } from "@/components/common/TableLevelBadges";
import { clearTdClass, rankTdClass } from "@/components/dashboard/ScoreUpdates";
import type { GoalRecord } from "@/hooks/use-goals";
import { useDeleteGoal } from "@/hooks/use-goals";
import { useFumenTableLevels } from "@/hooks/use-fumen-table-levels";
import { formatRatePercent } from "@/lib/rate-format";
import { formatTableLevelWithSymbolForDisplay } from "@/lib/table-level-display";
import { sortTableLevelsCore } from "@/lib/table-level-sort-core.mjs";
import { songHref } from "@/lib/song-href";
import { cn } from "@/lib/utils";

function clearLabel(clientType: string, clearType: number): string {
  const labels =
    clientType === "lr2" ? LR2_CLEAR_TYPE_LABELS : clientType === "beatoraja" ? BEATORAJA_CLEAR_TYPE_LABELS : CLEAR_TYPE_LABELS;
  return labels[clearType] ?? CLEAR_TYPE_LABELS[clearType] ?? String(clearType);
}

/** Course goals collapse NORMAL down to a generic "CLEAR" label — mirrors
 * `courseClearLabel` in the goal-setup wizard, since courses only ever
 * target a plain clear (not a specific lamp) at that level. */
function conditionClearLabel(goal: GoalRecord, clearType: number): string {
  if (goal.goal_type === "course" && clearType === 4) return "CLEAR";
  return clearLabel(goal.client_type, clearType);
}

/** Individual level pills for the tables a chart belongs to, styled the same
 * as the goal-setup wizard's per-table candidate badges. */
function ChartLevelBadges({ levels, maxVisible }: { levels: TableLevelRef[]; maxVisible: number }) {
  if (levels.length === 0) return null;
  const sorted = sortTableLevelsCore(levels) as TableLevelRef[];
  const visible = sorted.slice(0, maxVisible);
  const rest = sorted.length - visible.length;
  return (
    <>
      {visible.map((lv, i) => (
        <span
          key={`${lv.slug}-${lv.level}-${i}`}
          className="shrink-0 rounded-md border border-primary/40 bg-primary/10 px-1.5 py-0.5 text-caption font-semibold text-primary"
        >
          {formatTableLevelWithSymbolForDisplay({ tableSlug: lv.slug, tableSymbol: lv.symbol, level: lv.level })}
        </span>
      ))}
      {rest > 0 && <span className="shrink-0 text-caption text-muted-foreground">+{rest}</span>}
    </>
  );
}

interface GoalCardProps {
  goal: GoalRecord;
  /** Tighter, delete-button-less rendering for the profile card's goal preview. */
  compact?: boolean;
}

export function GoalCard({ goal, compact = false }: GoalCardProps) {
  const { t } = useTranslation();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const deleteGoal = useDeleteGoal();

  const title = goal.goal_type === "chart" ? goal.title : goal.course_name;
  const href =
    goal.goal_type === "chart" && (goal.fumen_sha256 || goal.fumen_md5)
      ? songHref({ sha256: goal.fumen_sha256, md5: goal.fumen_md5 })
      : null;

  // All tables the chart belongs to (not just the one it was targeted through) — same
  // source as the song detail page's "belonging tables" section.
  const chartTableLevels = useFumenTableLevels(
    goal.goal_type === "chart" ? goal.fumen_sha256 : null,
    goal.goal_type === "chart" ? goal.fumen_md5 : null,
  );

  function handleDelete() {
    deleteGoal.mutate(goal.goal_id, { onSuccess: () => setConfirmOpen(false) });
  }

  return (
    <div
      className={cn(
        "flex items-start justify-between gap-3 rounded-lg border border-border bg-card/60",
        compact ? "px-3 py-2" : "px-4 py-3",
      )}
    >
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-1.5">
          {goal.goal_type === "chart" ? (
            <ChartLevelBadges levels={chartTableLevels} maxVisible={compact ? 2 : 3} />
          ) : (
            goal.dan_title && (
              <span className="shrink-0 rounded-md border border-accent/40 bg-accent/10 px-1.5 py-0.5 text-caption font-semibold text-accent">
                {goal.dan_title}
              </span>
            )
          )}
          {href ? (
            <a href={href} className={cn("truncate font-semibold hover:text-primary", compact ? "text-label" : "text-body")}>
              {title}
            </a>
          ) : (
            <span className={cn("truncate font-semibold", compact ? "text-label" : "text-body")}>{title}</span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="rounded-full border border-border/60 bg-secondary/50 px-2 py-0.5 text-caption font-medium uppercase text-muted-foreground">
            {goal.client_type}
          </span>
          {goal.target_clear_type != null && (
            <span className={cn("rounded-md px-2 py-0.5 text-caption font-semibold", clearTdClass(goal.target_clear_type))}>
              {conditionClearLabel(goal, goal.target_clear_type)}
            </span>
          )}
          {goal.target_min_bp != null && (
            <span className="rounded-md bg-secondary/60 px-2 py-0.5 text-caption font-medium">
              BP {goal.target_min_bp}
            </span>
          )}
          {goal.target_rank != null && (
            <span className={cn("rounded-md px-2 py-0.5 text-caption font-semibold", rankTdClass(goal.target_rank))}>
              {goal.target_rank}
            </span>
          )}
          {goal.target_rate != null && (
            <span className="rounded-md bg-secondary/60 px-2 py-0.5 text-caption font-medium">
              {formatRatePercent(goal.target_rate)}
            </span>
          )}
          {goal.target_clear_type == null && goal.target_min_bp == null && goal.target_rank == null && goal.target_rate == null && (
            <span className="text-caption text-muted-foreground">{t("goals.card.noMetrics")}</span>
          )}
        </div>
        {!compact && goal.comment && <p className="truncate text-caption text-muted-foreground">{goal.comment}</p>}
        {!compact && goal.status === "achieved" && goal.achieved_recorded_at && (
          <p className="text-caption text-muted-foreground">
            {t("goals.card.achievedOn", { date: goal.achieved_recorded_at.slice(0, 10) })}
          </p>
        )}
      </div>

      {!compact && (
        <Button
          variant="ghost"
          size="icon"
          className="shrink-0 text-muted-foreground hover:text-destructive"
          aria-label={t("goals.card.deleteAria")}
          onClick={() => setConfirmOpen(true)}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      )}

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
