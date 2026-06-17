"use client";

import { ChevronLeft, ChevronRight, ChevronsRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

interface Props {
  periodStart: string;
  periodEnd: string;
  isCurrent: boolean;
  weekNumber: number | null;
  isAtFirstPeriod: boolean;
  offset: number;
  onOffsetChange: (offset: number) => void;
  onCurrentPeriodClick: () => void;
}

function fmt(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}`;
}

export function WeeklyPeriodNav({
  periodStart,
  periodEnd,
  isCurrent,
  weekNumber,
  isAtFirstPeriod,
  offset,
  onOffsetChange,
  onCurrentPeriodClick,
}: Props) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-center gap-2 flex-wrap">
      <button
        onClick={() => onOffsetChange(offset - 1)}
        disabled={isAtFirstPeriod}
        className={cn(
          "flex items-center justify-center w-9 h-9 rounded-lg border border-border transition-colors",
          isAtFirstPeriod ? "opacity-30 cursor-not-allowed" : "hover:bg-secondary",
        )}
        aria-label={t("weekly.prevWeek")}
      >
        <ChevronLeft className="h-4 w-4" />
      </button>

      <div className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border bg-secondary/40 min-w-[220px] justify-center">
        <span className="text-sm font-medium tabular-nums">
          {fmt(periodStart)}
        </span>
        <span className="text-muted-foreground text-sm">~</span>
        <span className="text-sm font-medium tabular-nums">
          {fmt(periodEnd)}
        </span>
        {weekNumber !== null && (
          <span
            className={cn(
              "ml-1 text-[11px] font-semibold rounded-full px-2 py-0.5",
              isCurrent ? "text-primary bg-primary/10" : "text-muted-foreground bg-muted",
            )}
          >
            {t("weekly.weekNumber", { count: weekNumber })}
          </span>
        )}
      </div>

      <button
        onClick={() => onOffsetChange(offset + 1)}
        disabled={isCurrent}
        className={cn(
          "flex items-center justify-center w-9 h-9 rounded-lg border border-border transition-colors",
          isCurrent ? "opacity-30 cursor-not-allowed" : "hover:bg-secondary",
        )}
        aria-label={t("weekly.nextWeek")}
      >
        <ChevronRight className="h-4 w-4" />
      </button>

      <button
        onClick={onCurrentPeriodClick}
        disabled={isCurrent}
        className={cn(
          "flex items-center justify-center w-9 h-9 rounded-lg border border-border transition-colors",
          isCurrent ? "opacity-30 cursor-not-allowed" : "hover:bg-secondary",
        )}
        aria-label={t("weekly.goToCurrent")}
        title={t("weekly.goToCurrent")}
      >
        <ChevronsRight className="h-4 w-4" />
      </button>
    </div>
  );
}
