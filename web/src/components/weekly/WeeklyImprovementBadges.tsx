"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { clearTypeLabel } from "@/lib/weekly-clear";
import type { RecordImprovement } from "@/lib/weekly-types";

interface Props {
  improvement: RecordImprovement | null;
  compact?: boolean;
}

function formatRateDelta(value: number): string {
  const percent = value * 100;
  return `${percent > 0 ? "+" : ""}${percent.toFixed(2)}%`;
}

function DeltaBadge({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-accent/30 bg-accent/10 px-2 py-0.5 text-xs font-semibold text-accent">
      {children}
    </span>
  );
}

function InlineComparison({
  previous,
  current,
}: {
  previous: ReactNode;
  current: ReactNode;
}) {
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap">
      <span className="opacity-70">{previous}</span>
      <span className="opacity-70">→</span>
      <span>{current}</span>
    </span>
  );
}

export function WeeklyImprovementBadges({ improvement, compact }: Props) {
  if (!improvement) return null;

  const prev = improvement.previous;
  const cur = improvement.current;
  const badges: ReactNode[] = [];

  if (improvement.clear_type_changed && prev?.clear_type != null && cur.clear_type != null) {
    badges.push(
      <DeltaBadge key="clear">
        <InlineComparison
          previous={clearTypeLabel(prev.clear_type).label}
          current={clearTypeLabel(cur.clear_type).label}
        />
      </DeltaBadge>,
    );
  }
  if (improvement.exscore_delta != null && improvement.exscore_delta > 0) {
    badges.push(<DeltaBadge key="ex">EX +{improvement.exscore_delta}</DeltaBadge>);
  }
  if (improvement.min_bp_delta != null && improvement.min_bp_delta < 0) {
    badges.push(<DeltaBadge key="bp">BP ▼{Math.abs(improvement.min_bp_delta)}</DeltaBadge>);
  }
  if (improvement.rate_delta != null && improvement.rate_delta > 0) {
    badges.push(<DeltaBadge key="rate">Rate {formatRateDelta(improvement.rate_delta)}</DeltaBadge>);
  }
  if (improvement.rank_changed && prev?.rank && cur.rank) {
    badges.push(
      <DeltaBadge key="rank">
        <InlineComparison previous={prev.rank} current={cur.rank} />
      </DeltaBadge>,
    );
  }

  if (badges.length === 0) return null;
  return <div className={cn("flex flex-wrap items-center gap-1.5", compact && "gap-1")}>{badges}</div>;
}
