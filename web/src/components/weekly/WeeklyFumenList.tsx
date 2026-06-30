"use client";

import { useMemo } from "react";
import { WeeklyFumenCard } from "./WeeklyFumenCard";
import { formatTableLevelForDisplay } from "@/lib/table-level-display";
import type { WeeklyFumenItem } from "@/lib/weekly-types";

interface Props {
  weeklyId: string;
  fumens: WeeklyFumenItem[];
  myUserId: string | null;
}

function extractLevelNum(item: WeeklyFumenItem): number {
  const stripped = formatTableLevelForDisplay({ tableSymbol: item.table_symbol, level: item.level });
  const match = stripped.match(/([\d.]+)(\+?)/);
  if (!match) return 0;
  return parseFloat(match[1]) + (match[2] === "+" ? 0.5 : 0);
}

/**
 * Symbol sort priority within the ★/▼ group (lower = first).
 * ★★ is handled separately as its own trailing group.
 */
function symbolPriority(symbol: string | null): number {
  if (symbol === "★") return 0;
  if (symbol === "▼") return 1;
  return 0;
}

function compareFumens(a: WeeklyFumenItem, b: WeeklyFumenItem): number {
  const aOvj = a.table_symbol === "★★";
  const bOvj = b.table_symbol === "★★";

  // ★★ always after ★ / ▼
  if (aOvj !== bOvj) return aOvj ? 1 : -1;

  // Within same group: sort by level number ascending
  const diff = extractLevelNum(a) - extractLevelNum(b);
  if (diff !== 0) return diff;

  // Same level: ★ before ▼
  return symbolPriority(a.table_symbol) - symbolPriority(b.table_symbol);
}

export function WeeklyFumenList({ weeklyId, fumens, myUserId }: Props) {
  const sorted = useMemo(() => [...fumens].sort(compareFumens), [fumens]);

  return (
    <div className="space-y-2">
      {sorted.map((item) => (
        <WeeklyFumenCard key={item.fumen_id} weeklyId={weeklyId} item={item} myUserId={myUserId} />
      ))}
    </div>
  );
}
