"use client";

import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useRatingBreakdown, type AggregatedRatingUpdateTable } from "@/hooks/use-analysis";
import { useMyRank } from "@/hooks/use-rankings";
import type { RankingTableConfig, RatingContributionSortBy, RatingHistoryMetric } from "@/lib/ranking-types";
import { cn } from "@/lib/utils";
import { ContributionTable } from "./ContributionTable";
import { BmsforceBreakdownCard } from "./BmsforceBreakdownCard";
import { RatingExpProgressBar } from "./RatingExpProgressBar";
import { MetricInfoIcon, type RatingMetricKey } from "./RatingMetricInfo";

function formatDelta(value: number, digits: number): string {
  if (Math.abs(value) < 1e-9) return "-";
  if (digits === 0) {
    const rounded = Math.round(Math.abs(value));
    return `${value > 0 ? "+" : "-"}${rounded.toLocaleString()}`;
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}`;
}

function entryKey(sha256: string | null, md5: string | null): string {
  return sha256 ?? md5 ?? "";
}

function displayMetricValue(value: number, digits: number): number {
  if (digits === 0) return Math.round(value);
  return Number(value.toFixed(digits));
}

function SummaryCard({
  label,
  infoMetric,
  previous,
  current,
  digits,
  extra,
  loading,
  selected,
  onSelect,
}: {
  label: ReactNode;
  infoMetric?: Exclude<RatingMetricKey, "level_mult">;
  previous: number | null;
  current: number | null;
  digits: number;
  extra?: string;
  loading?: boolean;
  selected: boolean;
  onSelect: () => void;
}) {
  const hasPrev = previous !== null && current !== null;
  const previousDisplay = previous === null ? null : displayMetricValue(previous, digits);
  const currentDisplay = current === null ? null : displayMetricValue(current, digits);
  const delta = hasPrev && previousDisplay !== null && currentDisplay !== null ? currentDisplay - previousDisplay : 0;
  const isZero = !hasPrev || delta === 0;
  const showLoading = loading && current === null;

  function formatValue(v: number): string {
    if (digits === 0) return Math.round(v).toLocaleString();
    return v.toFixed(digits);
  }

  const caption = current === null
    ? "-"
    : !hasPrev
      ? "비교 기준 없음"
      : isZero
      ? formatValue(currentDisplay!)
      : `${formatValue(previousDisplay!)} → ${formatValue(currentDisplay!)}`;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect();
        }
      }}
      aria-pressed={selected}
      className={cn(
        "h-full rounded-lg border px-4 py-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
        selected
          ? "border-primary bg-primary/10 ring-2 ring-primary/30"
          : "border-border/60 bg-secondary/20 hover:border-border hover:bg-secondary/35",
      )}
    >
      <div className="flex items-center gap-1.5 text-label text-muted-foreground">
        <span>{label}</span>
        {infoMetric ? <MetricInfoIcon metric={infoMetric} /> : null}
      </div>

      {showLoading ? (
        <div className="mt-1 h-7 w-16 animate-pulse rounded bg-secondary/60" />
      ) : (
        <p
          className={cn(
            "text-stat font-bold",
            !isZero && delta > 0 && "text-primary",
            !isZero && delta < 0 && "text-destructive",
          )}
        >
          {isZero ? "-" : formatDelta(delta, digits)}
        </p>
      )}

      <p className="text-caption text-muted-foreground">
        {showLoading ? (
          <span className="inline-block h-3 w-20 animate-pulse rounded bg-secondary/60 align-middle" />
        ) : (
          caption
        )}
      </p>
      {extra && <p className="text-caption text-muted-foreground">{extra}</p>}
    </div>
  );
}

interface RatingChangeTabContentProps {
  date: string;
  tables: RankingTableConfig[];
  selectedTableSlug: string | null;
  onSelectTable: (slug: string) => void;
  aggregatedTables?: AggregatedRatingUpdateTable[];
  enableMyRankFallback?: boolean;
  userId?: string | null;
  /** Controlled metric selection. If provided, internal useState is not used. */
  metric?: RatingHistoryMetric;
  /** Called when user changes metric. Required when `metric` prop is provided. */
  onMetricChange?: (metric: RatingHistoryMetric) => void;
}

export function RatingChangeTabContent({
  date,
  tables,
  selectedTableSlug,
  onSelectTable,
  aggregatedTables = [],
  enableMyRankFallback = false,
  userId,
  metric: metricProp,
  onMetricChange,
}: RatingChangeTabContentProps) {
  const [metricLocal, setMetricLocal] = useState<RatingHistoryMetric>("rating");
  // Controlled: use prop when provided; otherwise use local state
  const metric = metricProp !== undefined ? metricProp : metricLocal;
  function setMetric(m: RatingHistoryMetric) {
    if (onMetricChange) onMetricChange(m);
    else setMetricLocal(m);
  }
  const [sortBy, setSortBy] = useState<RatingContributionSortBy>("value");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const chipTables = aggregatedTables.length > 0
    ? aggregatedTables
    : tables.map((table) => ({
        table_slug: table.slug,
        display_name: table.display_name,
        count: 0,
        display_order: table.display_order,
      }));
  const fallbackTableSlug = chipTables[0]?.table_slug ?? null;
  const resolvedTableSlug = useMemo(() => {
    if (!selectedTableSlug) return fallbackTableSlug;
    const selectedExists = chipTables.some((table) => table.table_slug === selectedTableSlug);
    if (!selectedExists) return fallbackTableSlug;
    return selectedTableSlug;
  }, [chipTables, fallbackTableSlug, selectedTableSlug]);
  const selectedTable = useMemo(
    () => tables.find((table) => table.slug === resolvedTableSlug) ?? null,
    [resolvedTableSlug, tables],
  );
  const breakdown = useRatingBreakdown({ tableSlug: resolvedTableSlug, date, userId: userId ?? undefined });
  const myRank = useMyRank(enableMyRankFallback ? resolvedTableSlug : null, userId ?? undefined);

  const currentTableCount = useMemo(
    () => aggregatedTables.find((table) => table.table_slug === resolvedTableSlug)?.count ?? 0,
    [aggregatedTables, resolvedTableSlug],
  );
  const hasUpdatesElsewhere = aggregatedTables.length > 0 && currentTableCount === 0;
  const previousSnapshot = breakdown.data?.previous ?? null;
  const currentSnapshot = breakdown.data?.current ?? (
    myRank.data
      ? {
          exp: myRank.data.exp,
          exp_level: myRank.data.exp_level,
          is_max_level: myRank.data.is_max_level,
          max_level: myRank.data.max_level,
          exp_level_progress_ratio: myRank.data.exp_level_progress_ratio,
          exp_to_next_level: myRank.data.exp_to_next_level,
          exp_level_current_span: myRank.data.exp_level_current_span,
          rating: myRank.data.rating,
          rating_norm: myRank.data.bms_force,
        }
      : null
  );
  const summaryLoading = breakdown.isLoading && currentSnapshot === null;
  const expExtra = currentSnapshot
    ? previousSnapshot && previousSnapshot.exp_level !== currentSnapshot.exp_level
      ? `Lv.${previousSnapshot.exp_level} → Lv.${currentSnapshot.exp_level}`
      : `Lv.${currentSnapshot.exp_level}`
    : undefined;
  const ratingEntries = useMemo(
    () => breakdown.data?.rating_contributions ?? [],
    [breakdown.data?.rating_contributions],
  );
  const previousTopKeys = useMemo(
    () => new Set(ratingEntries.filter((entry) => entry.was_in_top_n).map((entry) => entryKey(entry.sha256, entry.md5))),
    [ratingEntries],
  );
  const currentTopKeys = useMemo(
    () => new Set(ratingEntries.filter((entry) => entry.is_in_top_n).map((entry) => entryKey(entry.sha256, entry.md5))),
    [ratingEntries],
  );

  useEffect(() => {
    if (!resolvedTableSlug || resolvedTableSlug === selectedTableSlug) return;
    onSelectTable(resolvedTableSlug);
  }, [onSelectTable, resolvedTableSlug, selectedTableSlug]);

  const metricLabel = metric === "exp"
    ? "경험치"
    : metric === "rating"
      ? "레이팅"
      : "BMSFORCE";
  const emptyMessage = hasUpdatesElsewhere
    ? `선택한 난이도표에는 ${metricLabel} 기여 변화가 없습니다. 위의 다른 난이도표를 선택해 보세요.`
    : `해당 날짜에는 ${metricLabel} 기여 변화가 없습니다.`;

  function handleSortChange(nextSortBy: RatingContributionSortBy) {
    if (metric !== "exp") return;
    if (nextSortBy === sortBy) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortBy(nextSortBy);
    setSortDir("desc");
  }

  if (tables.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border px-6 py-10 text-center text-body text-muted-foreground">
        레이팅 연동 난이도표가 없습니다.
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={150}>
      <div className="space-y-4">
        <div className="flex flex-wrap justify-center gap-2">
          {chipTables.map((table) => (
            <button
              key={table.table_slug}
              type="button"
              onClick={() => onSelectTable(table.table_slug)}
              className={cn(
                "inline-flex items-center gap-2 rounded-full border px-4 py-2 text-body font-medium transition-colors",
                table.table_slug === resolvedTableSlug
                  ? "border-primary bg-primary/15 text-primary"
                  : "border-border bg-secondary text-foreground hover:bg-secondary/70",
              )}
            >
              <span>{table.display_name}</span>
              <span className="tabular-nums font-semibold opacity-90">{table.count}</span>
              {breakdown.isFetching && table.table_slug === resolvedTableSlug && (
                <span className="text-caption text-muted-foreground">로딩 중</span>
              )}
            </button>
          ))}
        </div>

        <div className="grid items-stretch gap-3 md:grid-cols-3">
          <SummaryCard
            label="경험치"
            infoMetric="exp"
            previous={previousSnapshot?.exp ?? null}
            current={currentSnapshot?.exp ?? null}
            digits={0}
            extra={expExtra}
            loading={summaryLoading}
            selected={metric === "exp"}
            onSelect={() => setMetric("exp")}
          />
          <SummaryCard
            label={selectedTable ? `TOP ${selectedTable.top_n} 레이팅 합산` : "TOP 레이팅 합산"}
            infoMetric="rating"
            previous={previousSnapshot?.rating ?? null}
            current={currentSnapshot?.rating ?? null}
            digits={0}
            loading={summaryLoading}
            selected={metric === "rating"}
            onSelect={() => setMetric("rating")}
          />
          <SummaryCard
            label="BMSFORCE"
            infoMetric="bmsforce"
            previous={previousSnapshot?.rating_norm ?? null}
            current={currentSnapshot?.rating_norm ?? null}
            digits={3}
            loading={summaryLoading}
            selected={metric === "bmsforce"}
            onSelect={() => setMetric("bmsforce")}
          />
        </div>

        {currentSnapshot && (
          <div className="rounded-lg border border-border/60 bg-secondary/20 px-4 py-4">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-label text-muted-foreground">경험치 진행도</p>
              <p className="text-caption text-muted-foreground">
                현재 레벨 Lv.{currentSnapshot.exp_level}
                {currentSnapshot.is_max_level ? " MAX" : ""}
              </p>
            </div>
            <RatingExpProgressBar
              progressRatio={currentSnapshot.exp_level_progress_ratio}
              expToNextLevel={currentSnapshot.exp_to_next_level}
              previousProgressRatio={previousSnapshot?.exp_level_progress_ratio ?? null}
              previousLevel={previousSnapshot?.exp_level ?? null}
              currentLevel={currentSnapshot.exp_level}
              isMaxLevel={currentSnapshot.is_max_level}
              maxLevel={currentSnapshot.max_level}
            />
          </div>
        )}

        {breakdown.isLoading && !breakdown.data ? (
          <div className="h-64 animate-pulse rounded-lg bg-secondary/40" />
        ) : breakdown.error ? (
          <div className="rounded-lg border border-dashed border-border px-6 py-10 text-center text-body text-muted-foreground">
            레이팅 변동 데이터를 불러오지 못했습니다.
          </div>
        ) : breakdown.data ? (
          <>
            {metric === "bmsforce" ? (
              <BmsforceBreakdownCard breakdown={breakdown.data.bmsforce_breakdown} />
            ) : (
              <ContributionTable
                entries={metric === "exp" ? breakdown.data.exp_contributions : breakdown.data.rating_contributions}
                metric={metric}
                emptyMessage={emptyMessage}
                totalEntries={metric === "exp"
                  ? (breakdown.data.exp_total_entries ?? breakdown.data.exp_contributions.length)
                  : (breakdown.data.rating_total_entries ?? breakdown.data.rating_contributions.length)}
                previousTopKeys={metric === "rating" ? previousTopKeys : undefined}
                currentTopKeys={metric === "rating" ? currentTopKeys : undefined}
                topN={selectedTable?.top_n}
                allowSort={metric === "exp"}
                sortBy={sortBy}
                sortDir={sortDir}
                onSortChange={handleSortChange}
                presentation="day-detail"
              />
            )}
          </>
        ) : (
          <div className="rounded-lg border border-dashed border-border px-6 py-10 text-center text-body text-muted-foreground">
            레이팅 변동을 표시할 난이도표를 선택해주세요.
          </div>
        )}
      </div>
    </TooltipProvider>
  );
}
