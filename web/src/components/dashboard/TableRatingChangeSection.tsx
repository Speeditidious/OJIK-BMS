"use client";

import { useTranslation } from "react-i18next";
import { useRatingBreakdown } from "@/hooks/use-analysis";
import { RatingExpProgressBar } from "@/components/ranking/RatingExpProgressBar";
import { RatingContributionGrid } from "@/components/ranking/RatingContributionGrid";
import { cn } from "@/lib/utils";

function formatSigned(v: number, decimals = 3): string {
  if (Math.abs(v) < 1e-9) return "-";
  return `${v > 0 ? "+" : ""}${v.toFixed(decimals)}`;
}

interface TableRatingChangeSectionProps {
  tableSlug: string;
  tableDisplayName: string;
  date: string;
  userId: string;
  showExpInfo: boolean;
  showRatingInfo?: boolean;
  ratingOrder?: ("exp_info" | "rating_info")[];
  enabled?: boolean;
}

export function TableRatingChangeSection({
  tableSlug,
  tableDisplayName,
  date,
  userId,
  showExpInfo,
  showRatingInfo = true,
  ratingOrder = ["exp_info", "rating_info"],
  enabled = true,
}: TableRatingChangeSectionProps) {
  const { t } = useTranslation();
  const { data, isLoading } = useRatingBreakdown({ tableSlug, date, userId, enabled });

  if (isLoading) {
    return (
      <div className="space-y-2 animate-pulse">
        <div className="h-3 w-24 rounded bg-muted" />
        <div className="h-6 w-40 rounded bg-muted" />
        <div className="h-32 rounded-xl bg-muted" />
      </div>
    );
  }

  if (!data) return null;

  const prev = data.previous;
  const curr = data.current;

  const expDelta = curr.exp - prev.exp;
  const ratingDelta = curr.rating - prev.rating;
  const bmsforce = data.bmsforce_breakdown;
  const bmsforceChanged = Math.abs(bmsforce.total) > 1e-9;

  const hasExpChange = Math.abs(expDelta) > 1e-9;
  const hasRatingChange = Math.abs(ratingDelta) > 1e-9;
  const hasBmsforceChange = bmsforceChanged;
  const hasAnyChange = hasRatingChange || hasBmsforceChange || (showExpInfo && hasExpChange);

  if (!hasAnyChange) return null;

  // Rating + BMSFORCE delta tiles. `numberCls` tunes the headline size so the
  // block height can be matched to the EXP block when shown side-by-side.
  const deltaTiles = (numberCls: string) => (
    <div className="grid h-full grid-cols-2 gap-3">
      <div className="flex flex-col justify-center rounded-xl border border-border/50 bg-secondary/30 px-4 py-3">
        <p className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
          {t("dashboard.daySheet.topNRating")}
        </p>
        <p
          className={cn(
            "mt-1 font-extrabold tabular-nums leading-none",
            numberCls,
            hasRatingChange ? "text-foreground" : "text-muted-foreground/60",
          )}
        >
          {hasRatingChange ? formatSigned(ratingDelta) : "-"}
        </p>
      </div>
      <div className="flex flex-col justify-center rounded-xl border border-border/50 bg-secondary/30 px-4 py-3">
        <p className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
          {t("dashboard.daySheet.bmsforceChange")}
        </p>
        <p
          className={cn(
            "mt-1 font-extrabold tabular-nums leading-none",
            numberCls,
            hasBmsforceChange ? "text-foreground" : "text-muted-foreground/60",
          )}
          style={hasBmsforceChange && bmsforce.total > 0 ? { color: "hsl(var(--accent))" } : undefined}
        >
          {hasBmsforceChange ? formatSigned(bmsforce.total) : "-"}
        </p>
      </div>
    </div>
  );

  // Summary card. Rendered as the floated leading slot so the rating-change cards
  // flow beside and below it. With EXP shown: EXP on the left, deltas on the right
  // (side-by-side, equal height). Without EXP: deltas fill the card at full size.
  const showSummaryCard = showExpInfo || showRatingInfo;

  const expBlock = (
    <div className={cn("flex flex-col justify-center gap-2", showRatingInfo ? "lg:w-1/2" : "w-full")}>
      <div className="flex items-baseline gap-1.5 flex-wrap">
        <span className="text-[26px] font-extrabold tabular-nums text-foreground leading-none">
          Lv.{curr.exp_level}
        </span>
      </div>
      <RatingExpProgressBar
        progressRatio={curr.exp_level_progress_ratio}
        expToNextLevel={curr.exp_to_next_level}
        previousProgressRatio={prev.exp_level_progress_ratio}
        previousLevel={prev.exp_level}
        currentLevel={curr.exp_level}
        isMaxLevel={curr.is_max_level}
        maxLevel={curr.max_level}
        expDelta={hasExpChange ? expDelta : null}
      />
    </div>
  );

  const ratingBlock = showRatingInfo ? (
    <div className="lg:w-1/2">{deltaTiles("text-[28px]")}</div>
  ) : null;

  const expFirst = ratingOrder[0] === "exp_info";

  const summaryCard = showSummaryCard ? (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-border/50 bg-card">
      {showExpInfo ? (
        <div className="flex flex-1 flex-col gap-4 p-4 lg:flex-row lg:items-stretch">
          {expFirst ? expBlock : ratingBlock}
          {expFirst ? ratingBlock : expBlock}
        </div>
      ) : (
        <div className="flex flex-1 flex-col p-4">{deltaTiles("text-[40px]")}</div>
      )}
    </div>
  ) : undefined;

  return (
    <div className="space-y-3">
      <h4
        data-day-sheet-split-block
        data-day-sheet-keep-with-next
        className="text-2xl font-extrabold text-foreground tracking-tight"
      >
        {tableDisplayName}
      </h4>

      {/* Summary card (floated) + contribution cards flowing beside / below */}
      <RatingContributionGrid entries={data.rating_contributions} leadingSlot={summaryCard} />
    </div>
  );
}
