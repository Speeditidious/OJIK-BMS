"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

interface Props {
  periodStart: string;
  periodEnd: string;
  isCurrent: boolean;
  offset: number;
  onOffsetChange: (offset: number) => void;
}

function fmt(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}`;
}

export function WeeklyPeriodNav({ periodStart, periodEnd, isCurrent, offset, onOffsetChange }: Props) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-center gap-2">
      <button
        onClick={() => onOffsetChange(offset - 1)}
        className="flex items-center justify-center w-9 h-9 rounded-lg border border-border hover:bg-secondary transition-colors"
        aria-label={t("weekly.prevWeek")}
      >
        <ChevronLeft className="h-4 w-4" />
      </button>

      <div className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border bg-secondary/40 min-w-[200px] justify-center">
        <span className="text-sm font-medium tabular-nums">
          {fmt(periodStart)}
        </span>
        <span className="text-muted-foreground text-sm">~</span>
        <span className="text-sm font-medium tabular-nums">
          {fmt(periodEnd)}
        </span>
        {isCurrent && (
          <span className="ml-1 text-[11px] font-semibold text-primary bg-primary/10 rounded-full px-2 py-0.5">
            {t("weekly.thisWeek")}
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
    </div>
  );
}
