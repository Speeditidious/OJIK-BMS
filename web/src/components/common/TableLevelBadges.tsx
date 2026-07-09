"use client";

import {
  compareByTableLevelsCore,
  sortTableLevelsCore,
} from "@/lib/table-level-sort-core.mjs";
import { formatTableLevelWithSymbolForDisplay } from "@/lib/table-level-display";
import { cn } from "@/lib/utils";

export interface TableLevelRef {
  symbol: string;
  slug: string;
  level: string;
}

export function compareByTableLevels(a: TableLevelRef[], b: TableLevelRef[]): number {
  return compareByTableLevelsCore(a, b);
}

interface Props {
  levels: TableLevelRef[];
  maxVisible?: number;
  className?: string;
}

export function TableLevelBadges({ levels, maxVisible = 3, className }: Props) {
  if (levels.length === 0) return <span className={cn("text-label row-muted", className)}>-</span>;
  const sortedLevels = sortTableLevelsCore(levels) as TableLevelRef[];
  const visible = sortedLevels.slice(0, maxVisible);
  const rest = sortedLevels.length - visible.length;
  const text = visible
    .map(({ symbol, slug, level }) => (
      formatTableLevelWithSymbolForDisplay({ tableSlug: slug, tableSymbol: symbol, level })
    ))
    .join(", ");
  return (
    <span className={cn("text-label", className)}>
      {text}
      {rest > 0 && <span className="text-caption row-muted"> +{rest}</span>}
    </span>
  );
}
