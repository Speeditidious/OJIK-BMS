"use client";

import { useEffect, useMemo, useRef } from "react";
import Link from "next/link";
import { useVirtualizer } from "@tanstack/react-virtual";
import { SourceClientBadge } from "@/components/common/SourceClientBadge";
import { clearText } from "@/components/dashboard/RecentActivity";
import { CLEAR_ROW_CLASS } from "@/lib/fumen-table-utils";
import type {
  RankingContributionEntry,
  RatingContributionMetric,
  RatingContributionSortBy,
} from "@/lib/ranking-types";
import { formatRateDelta, formatRatePercent } from "@/lib/rate-format";
import { cn } from "@/lib/utils";

const ROW_HEIGHT = 44;
const MAX_TABLE_HEIGHT = 420;
const TITLE_COLLATOR = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
const RANK_GRADE_ORDER: Record<string, number> = {
  F: 0,
  E: 1,
  D: 2,
  C: 3,
  B: 4,
  A: 5,
  AA: 6,
  AAA: 7,
  MAX: 8,
};

interface ContributionTableProps {
  entries: RankingContributionEntry[];
  metric: RatingContributionMetric;
  isLoading?: boolean;
  emptyMessage: string;
  totalEntries: number;
  previousTopKeys?: Set<string>;
  currentTopKeys?: Set<string>;
  topN?: number;
  allowSort?: boolean;
  sortBy?: RatingContributionSortBy;
  sortDir?: "asc" | "desc";
  onSortChange?: (sortBy: RatingContributionSortBy) => void;
  /**
   * "default"     — standard virtualized table (default)
   * "day-detail"  — comparison columns, center-aligned layout
   * "rating-detail" — no scroll/virtualization (for rating detail tab TOP view)
   */
  presentation?: "default" | "day-detail" | "rating-detail";
  userId?: string;
}

type SectionKey = "kept" | "entered" | "dropped";

type SectionRow =
  | { kind: "ellipsis"; id: string }
  | { kind: "entry"; id: string; entry: RankingContributionEntry };

interface SectionModel {
  section: SectionKey;
  count: number;
  averageDelta: number | null;
  rows: SectionRow[];
}

interface TableColumn {
  width?: number;
  align: "left" | "center";
}

const DEFAULT_COLUMNS: TableColumn[] = [
  { width: 72, align: "left" },
  { width: 84, align: "left" },
  { align: "left" },
  { width: 128, align: "left" },
  { width: 120, align: "left" },
  { width: 140, align: "left" },
  { width: 120, align: "left" },
  { width: 72, align: "left" },
  { width: 200, align: "center" },
];

const DAY_DETAIL_COLUMNS: TableColumn[] = [
  { width: 120, align: "left" },
  { width: 92, align: "left" },
  { align: "left" },
  { width: 160, align: "center" },
  { width: 140, align: "center" },
  { width: 200, align: "center" },
  { width: 116, align: "center" },
  { width: 72, align: "center" },
  { width: 220, align: "center" },
];

function contributionKey(entry: RankingContributionEntry): string {
  return entry.sha256 ?? entry.md5 ?? `${entry.rank}-${entry.title}`;
}

function compareNullableNumber(left: number | null | undefined, right: number | null | undefined): number {
  if (left == null && right == null) return 0;
  if (left == null) return 1;
  if (right == null) return -1;
  return left - right;
}

function compareNullableString(left: string | null | undefined, right: string | null | undefined): number {
  if (!left && !right) return 0;
  if (!left) return 1;
  if (!right) return -1;
  return TITLE_COLLATOR.compare(left, right);
}

function envLabelFromEntry(entry: RankingContributionEntry): string {
  if (entry.source_client) return entry.source_client;
  const unique = Array.from(new Set(entry.client_types.filter(Boolean)));
  if (unique.length === 0) return "";
  if (unique.length > 1) return "MIX";
  if (unique[0] === "lr2") return "LR";
  if (unique[0] === "beatoraja") return "BR";
  return unique[0]?.toUpperCase() ?? "";
}

function formatSigned(value: number, digits: number): string {
  if (Math.abs(value) < 1e-9) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}`;
}

function cellAlignClass(align: TableColumn["align"]): string {
  return align === "center" ? "text-center" : "text-left";
}

function comparisonEnabled(
  presentation: "default" | "day-detail" | "rating-detail",
  section: SectionKey | undefined,
  hasPrevious: boolean,
): boolean {
  if (!hasPrevious) return false;
  if (presentation === "day-detail") return true;
  return section === "kept";
}

function sectionDisplayRank(entry: RankingContributionEntry, section: SectionKey): number {
  return section === "dropped" ? entry.previous_rank ?? entry.rank : entry.rank;
}

function sectionMeta(section: SectionKey, topN?: number): { label: string; badgeClass: string; helperText?: string } {
  const topLabel = topN != null ? `TOP ${topN}` : "TOP";
  if (section === "kept") {
    return {
      label: `${topLabel} 내부 갱신`,
      badgeClass: "border-primary/30 bg-primary/10 text-primary",
    };
  }
  if (section === "entered") {
    return {
      label: `신규 진입 ${topLabel}`,
      badgeClass: "border-accent/35 bg-accent/10 text-accent",
    };
  }
  return {
    label: `${topLabel} 탈락`,
    badgeClass: "border-warning/35 bg-warning/10 text-warning",
  };
}

function levelSortValue(entry: RankingContributionEntry): number {
  const numeric = Number.parseFloat(entry.level.replace(/[^0-9.]/g, ""));
  if (Number.isFinite(numeric)) return numeric;
  return -1;
}

function compareEntries(
  left: RankingContributionEntry,
  right: RankingContributionEntry,
  sortBy: RatingContributionSortBy,
  sortDir: "asc" | "desc",
): number {
  let result = 0;

  if (sortBy === "value") {
    result = compareNullableNumber(left.value, right.value);
  } else if (sortBy === "rank") {
    result = compareNullableNumber(left.rank, right.rank);
  } else if (sortBy === "level") {
    result = compareNullableNumber(levelSortValue(left), levelSortValue(right));
  } else if (sortBy === "title") {
    result = compareNullableString(left.title, right.title);
  } else if (sortBy === "clear_type") {
    result = compareNullableNumber(left.clear_type, right.clear_type);
  } else if (sortBy === "min_bp") {
    result = compareNullableNumber(left.min_bp, right.min_bp);
  } else if (sortBy === "rate") {
    result = compareNullableNumber(left.rate, right.rate);
  } else if (sortBy === "rank_grade") {
    result = compareNullableNumber(
      left.rank_grade ? RANK_GRADE_ORDER[left.rank_grade] ?? -1 : null,
      right.rank_grade ? RANK_GRADE_ORDER[right.rank_grade] ?? -1 : null,
    );
  } else if (sortBy === "env") {
    result = compareNullableString(envLabelFromEntry(left), envLabelFromEntry(right));
  }

  if (result === 0) {
    result = compareNullableString(left.title, right.title);
  }
  if (result === 0) {
    result = compareNullableString(left.sha256 ?? left.md5, right.sha256 ?? right.md5);
  }

  return sortDir === "desc" ? result * -1 : result;
}

function SortIcon({
  isActive,
  sortDir,
}: {
  isActive: boolean;
  sortDir?: "asc" | "desc";
}) {
  if (!isActive) {
    return <span className="ml-0.5 text-muted-foreground/35">⇅</span>;
  }
  return <span className="ml-0.5 text-foreground">{sortDir === "asc" ? "↑" : "↓"}</span>;
}

function SortableHeader({
  label,
  sortKey,
  activeSort,
  sortDir,
  allowSort,
  onSortChange,
  className,
  title,
  align = "left",
}: {
  label: string;
  sortKey: RatingContributionSortBy;
  activeSort?: RatingContributionSortBy;
  sortDir?: "asc" | "desc";
  allowSort?: boolean;
  onSortChange?: (sortBy: RatingContributionSortBy) => void;
  className?: string;
  title?: string;
  align?: TableColumn["align"];
}) {
  const isActive = activeSort === sortKey;
  return (
    <div
      role="columnheader"
      aria-sort={allowSort ? (isActive ? (sortDir === "asc" ? "ascending" : "descending") : "none") : undefined}
      className={className}
    >
      <button
        type="button"
        title={title}
        className={cn(
          "w-full text-label font-medium text-muted-foreground",
          align === "center" ? "text-center" : "text-left",
          allowSort ? "transition-colors hover:text-foreground" : "cursor-default",
        )}
        onClick={() => allowSort && onSortChange?.(sortKey)}
      >
        {label}
        {allowSort && <SortIcon isActive={isActive} sortDir={sortDir} />}
      </button>
    </div>
  );
}

function InlineComparison({
  previous,
  current,
  diff,
}: {
  previous: React.ReactNode;
  current: React.ReactNode;
  diff?: React.ReactNode | null;
}) {
  return (
    <div className="inline-flex flex-wrap items-center gap-1 whitespace-nowrap">
      <span className="opacity-70">{previous}</span>
      <span className="opacity-70">→</span>
      <span className="font-semibold">{current}</span>
      {diff ? <span className="font-bold opacity-75">{diff}</span> : null}
    </div>
  );
}

function ValueFallback() {
  return <span className="row-prev">--</span>;
}

function RankCell({
  entry,
  section,
  presentation,
}: {
  entry: RankingContributionEntry;
  section?: SectionKey;
  presentation: "default" | "day-detail" | "rating-detail";
}) {
  const displayRank = section === "dropped" ? entry.previous_rank ?? entry.rank : entry.rank;
  const previousRank = entry.previous_rank ?? null;

  if (presentation === "day-detail") {
    if (previousRank != null && previousRank !== entry.rank) {
      return (
        <InlineComparison
          previous={previousRank}
          current={entry.rank}
        />
      );
    }
    return <span className="tabular-nums">{entry.rank}</span>;
  }

  if (section !== "kept" || previousRank == null || previousRank === entry.rank) {
    return <span className="tabular-nums">{displayRank}</span>;
  }

  const diff = previousRank - entry.rank;
  return (
    <div className="flex items-center gap-1 whitespace-nowrap tabular-nums">
      <span className="font-semibold">{entry.rank}</span>
      <span className="text-caption font-semibold text-muted-foreground">
        {diff > 0 ? `↑${diff}` : `↓${Math.abs(diff)}`}
      </span>
    </div>
  );
}

function ClearCell({
  entry,
  section,
  clientType,
  presentation,
}: {
  entry: RankingContributionEntry;
  section?: SectionKey;
  clientType: string;
  presentation: "default" | "day-detail" | "rating-detail";
}) {
  const previousClearType = entry.previous_clear_type ?? null;
  const effectivePresentation = presentation === "rating-detail" ? "default" : presentation;
  const showComparison = comparisonEnabled(effectivePresentation, section, previousClearType != null);

  if (!showComparison) {
    return clearText(entry.clear_type, clientType);
  }
  if (previousClearType == null) {
    return clearText(entry.clear_type, clientType);
  }
  if (previousClearType === entry.clear_type) {
    return clearText(entry.clear_type, clientType);
  }

  return (
    <InlineComparison
      previous={clearText(previousClearType, clientType)}
      current={clearText(entry.clear_type, clientType)}
    />
  );
}

function BpCell({
  entry,
  section,
  presentation,
}: {
  entry: RankingContributionEntry;
  section?: SectionKey;
  presentation: "default" | "day-detail" | "rating-detail";
}) {
  const showComparison = comparisonEnabled(
    presentation,
    section,
    entry.previous_min_bp != null && entry.min_bp != null,
  );

  if (entry.min_bp == null) {
    return <ValueFallback />;
  }
  if (!showComparison || entry.previous_min_bp == null) {
    return <span className="tabular-nums">{entry.min_bp}</span>;
  }
  if (entry.previous_min_bp === entry.min_bp) {
    return <span className="tabular-nums">{entry.min_bp}</span>;
  }

  const diff = entry.previous_min_bp - entry.min_bp;
  return (
    <InlineComparison
      previous={entry.previous_min_bp}
      current={entry.min_bp}
      diff={diff === 0 ? null : `${diff > 0 ? "▼" : "▲"}${Math.abs(diff)}`}
    />
  );
}

function RateCell({
  entry,
  section,
  presentation,
}: {
  entry: RankingContributionEntry;
  section?: SectionKey;
  presentation: "default" | "day-detail" | "rating-detail";
}) {
  const showComparison = comparisonEnabled(
    presentation,
    section,
    entry.previous_rate != null && entry.rate != null,
  );

  if (entry.rate == null) {
    return <ValueFallback />;
  }
  if (!showComparison || entry.previous_rate == null) {
    return <span className="tabular-nums">{formatRatePercent(entry.rate)}</span>;
  }
  if (Math.abs(entry.rate - entry.previous_rate) < 1e-9) {
    return <span className="tabular-nums">{formatRatePercent(entry.rate)}</span>;
  }

  const diff = entry.rate - entry.previous_rate;
  return (
    <InlineComparison
      previous={formatRatePercent(entry.previous_rate)}
      current={formatRatePercent(entry.rate)}
      diff={diff === 0 ? null : formatRateDelta(diff)}
    />
  );
}

function RankGradeCell({
  entry,
  section,
  presentation,
}: {
  entry: RankingContributionEntry;
  section?: SectionKey;
  presentation: "default" | "day-detail" | "rating-detail";
}) {
  const showComparison = comparisonEnabled(
    presentation,
    section,
    !!entry.previous_rank_grade && !!entry.rank_grade,
  );

  if (!entry.rank_grade) {
    return <ValueFallback />;
  }
  if (!showComparison || !entry.previous_rank_grade) {
    return <span>{entry.rank_grade}</span>;
  }
  if (entry.previous_rank_grade === entry.rank_grade) {
    return <span>{entry.rank_grade}</span>;
  }

  return (
    <InlineComparison
      previous={entry.previous_rank_grade}
      current={entry.rank_grade}
    />
  );
}

function formatValueMetric(v: number): string {
  return Math.round(v).toLocaleString();
}

function ValueCell({
  entry,
  metric,
  section,
  presentation,
}: {
  entry: RankingContributionEntry;
  metric: RatingContributionMetric;
  section?: SectionKey;
  presentation: "default" | "day-detail" | "rating-detail";
}) {
  const previousValue = entry.previous_value ?? null;
  const effectivePresentation = presentation === "rating-detail" ? "default" : presentation;
  const showComparison = comparisonEnabled(effectivePresentation, section, previousValue != null);
  const currentDisplayValue = Math.round(entry.value);
  const previousDisplayValue = previousValue == null ? null : Math.round(previousValue);

  if (!showComparison || previousValue == null) {
    return <span className="tabular-nums">{formatValueMetric(entry.value)}</span>;
  }
  const previousDisplay = previousDisplayValue ?? 0;
  if (previousDisplay === currentDisplayValue) {
    return <span className="tabular-nums">{currentDisplayValue.toLocaleString()}</span>;
  }
  const displayDelta = currentDisplayValue - previousDisplay;

  return (
    <InlineComparison
      previous={previousDisplay.toLocaleString()}
      current={currentDisplayValue.toLocaleString()}
      diff={
        `${displayDelta > 0 ? "▲" : "▼"}${Math.abs(displayDelta).toLocaleString()}`
      }
    />
  );
}

function ContributionRow({
  entry,
  metric,
  section,
  presentation,
  columns,
  userId,
}: {
  entry: RankingContributionEntry;
  metric: RatingContributionMetric;
  section?: SectionKey;
  presentation: "default" | "day-detail" | "rating-detail";
  columns: TableColumn[];
  userId?: string;
}) {
  const songHref = userId
    ? `/songs/${entry.sha256 ?? entry.md5}?user_id=${encodeURIComponent(userId)}`
    : `/songs/${entry.sha256 ?? entry.md5}`;
  const rowClass = CLEAR_ROW_CLASS[entry.clear_type] ?? "";
  const clearClient = entry.client_types[0] ?? "beatoraja";

  return (
    <tr
      style={{ height: ROW_HEIGHT }}
      className={cn("border-b border-border/30", rowClass || "hover:bg-secondary/50")}
    >
      <td className={cn("px-2 text-label tabular-nums", cellAlignClass(columns[0].align))}>
        <RankCell entry={entry} section={section} presentation={presentation} />
      </td>
      <td className={cn("px-2 text-label", cellAlignClass(columns[1].align))}>{entry.symbol}{entry.level}</td>
      <td className="px-2">
        <div className="min-w-0 overflow-hidden">
          <Link href={songHref} className="block max-w-full truncate text-label leading-tight transition-colors hover:text-primary">
            {entry.title}
          </Link>
          {entry.artist && (
            <div className="max-w-full truncate text-caption text-muted-foreground/80 row-muted">{entry.artist}</div>
          )}
        </div>
      </td>
      <td className={cn("px-2 text-label", cellAlignClass(columns[3].align))}>
        <ClearCell entry={entry} section={section} clientType={clearClient} presentation={presentation} />
      </td>
      <td className={cn("px-2 text-label", cellAlignClass(columns[4].align))}>
        <BpCell entry={entry} section={section} presentation={presentation} />
      </td>
      <td className={cn("px-2 text-label", cellAlignClass(columns[5].align))}>
        <RateCell entry={entry} section={section} presentation={presentation} />
      </td>
      <td className={cn("px-2 text-label", cellAlignClass(columns[6].align))}>
        <RankGradeCell entry={entry} section={section} presentation={presentation} />
      </td>
      <td className={cn("px-2 text-label", cellAlignClass(columns[7].align))}>
        {entry.updated_today === false ? (
          <span className="row-prev">—</span>
        ) : (
          <SourceClientBadge
            sourceClient={entry.source_client}
            sourceClientDetail={entry.source_client_detail}
            fallbackClientTypes={entry.client_types}
          />
        )}
      </td>
      <td className="rating-value-cell px-3 text-center w-32 font-bold tabular-nums text-base">
        <ValueCell entry={entry} metric={metric} section={section} presentation={presentation} />
      </td>
    </tr>
  );
}

function EllipsisRow({ colSpan }: { colSpan: number }) {
  return (
    <tr className="border-b border-border/20">
      <td
        colSpan={colSpan}
        aria-hidden="true"
        className="px-2 py-1 text-center text-label leading-none tracking-widest text-muted-foreground/80"
      >
        ⋮
      </td>
    </tr>
  );
}

function TableHeader({
  allowSort,
  sortBy,
  sortDir,
  onSortChange,
  valueLabel,
  columns,
}: {
  allowSort: boolean;
  sortBy: RatingContributionSortBy;
  sortDir: "asc" | "desc";
  onSortChange?: (sortBy: RatingContributionSortBy) => void;
  valueLabel: string;
  columns: TableColumn[];
}) {
  return (
    <thead className="sticky top-0 z-10 bg-background text-label text-foreground font-medium">
      <tr className="border-b border-border">
        <th className={cn("px-2 py-2 font-medium whitespace-nowrap", cellAlignClass(columns[0].align))}>
          <SortableHeader label="순위" sortKey="rank" activeSort={sortBy} sortDir={sortDir} allowSort={allowSort} onSortChange={onSortChange} align={columns[0].align} />
        </th>
        <th className={cn("px-2 py-2 font-medium whitespace-nowrap", cellAlignClass(columns[1].align))}>
          <SortableHeader label="레벨" sortKey="level" activeSort={sortBy} sortDir={sortDir} allowSort={allowSort} onSortChange={onSortChange} align={columns[1].align} />
        </th>
        <th className={cn("px-2 py-2 font-medium whitespace-nowrap", cellAlignClass(columns[2].align))}>
          <SortableHeader label="제목" sortKey="title" activeSort={sortBy} sortDir={sortDir} allowSort={allowSort} onSortChange={onSortChange} align={columns[2].align} />
        </th>
        <th className={cn("px-2 py-2 font-medium whitespace-nowrap", cellAlignClass(columns[3].align))}>
          <SortableHeader label="클리어" sortKey="clear_type" activeSort={sortBy} sortDir={sortDir} allowSort={allowSort} onSortChange={onSortChange} align={columns[3].align} />
        </th>
        <th className={cn("px-2 py-2 font-medium whitespace-nowrap", cellAlignClass(columns[4].align))}>
          <SortableHeader label="BP" sortKey="min_bp" activeSort={sortBy} sortDir={sortDir} allowSort={allowSort} onSortChange={onSortChange} align={columns[4].align} />
        </th>
        <th className={cn("px-2 py-2 font-medium whitespace-nowrap", cellAlignClass(columns[5].align))}>
          <SortableHeader label="판정" sortKey="rate" activeSort={sortBy} sortDir={sortDir} allowSort={allowSort} onSortChange={onSortChange} align={columns[5].align} />
        </th>
        <th className={cn("px-2 py-2 font-medium whitespace-nowrap", cellAlignClass(columns[6].align))}>
          <SortableHeader label="랭크" sortKey="rank_grade" activeSort={sortBy} sortDir={sortDir} allowSort={allowSort} onSortChange={onSortChange} align={columns[6].align} />
        </th>
        <th className={cn("px-2 py-2 font-medium whitespace-nowrap", cellAlignClass(columns[7].align))}>
          <SortableHeader
            label="구동기"
            sortKey="env"
            activeSort={sortBy}
            sortDir={sortDir}
            allowSort={allowSort}
            onSortChange={onSortChange}
            title="LR = LR2, BR = Beatoraja, MIX = 양쪽 기록"
            align={columns[7].align}
          />
        </th>
        <th className="px-2 py-2 font-bold whitespace-nowrap text-center w-32 text-base">
          <SortableHeader label={valueLabel} sortKey="value" activeSort={sortBy} sortDir={sortDir} allowSort={allowSort} onSortChange={onSortChange} align="center" />
        </th>
      </tr>
    </thead>
  );
}

function SectionCard({
  section,
  rows,
  count,
  averageDelta,
  colSpan,
  topN,
  valueLabel,
  presentation,
  userId,
}: {
  section: SectionKey;
  rows: SectionRow[];
  count: number;
  averageDelta: number | null;
  colSpan: number;
  topN?: number;
  valueLabel: string;
  presentation: "default" | "day-detail" | "rating-detail";
  userId?: string;
}) {
  const meta = sectionMeta(section, topN);
  const columns = presentation === "day-detail" ? DAY_DETAIL_COLUMNS : DEFAULT_COLUMNS;

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card/60">
      <div className="border-b border-border/50 bg-secondary/25 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className={cn("inline-flex rounded-full border px-2 py-0.5 text-caption font-medium", meta.badgeClass)}>
              {meta.label}
            </span>
            <span className="text-caption text-muted-foreground">{count}개</span>
          </div>
          {section === "kept" && averageDelta != null && (
            <span className="text-caption text-muted-foreground">
              평균 변동 {formatSigned(averageDelta, 2)}
            </span>
          )}
        </div>
        {meta.helperText && (
          <p className="mt-2 text-caption text-muted-foreground">{meta.helperText}</p>
        )}
      </div>

      <div className="overflow-auto">
        <table className="w-full border-collapse" style={{ tableLayout: "fixed", minWidth: 960 }}>
          <colgroup>
            {columns.map((column, index) => (
              <col key={index} style={column.width ? { width: column.width } : undefined} />
            ))}
          </colgroup>
          <TableHeader allowSort={false} sortBy="value" sortDir="desc" valueLabel={valueLabel} columns={columns} />
          <tbody>
            {rows.map((row) => (
              row.kind === "ellipsis"
                ? <EllipsisRow key={row.id} colSpan={colSpan} />
                : <ContributionRow key={row.id} entry={row.entry} metric="rating" section={section} presentation={presentation === "rating-detail" ? "default" : presentation} columns={columns} userId={userId} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ContributionTable({
  entries,
  metric,
  isLoading = false,
  emptyMessage,
  totalEntries,
  previousTopKeys,
  currentTopKeys,
  topN,
  allowSort = false,
  sortBy = "value",
  sortDir = "desc",
  onSortChange,
  presentation = "default",
  userId,
}: ContributionTableProps) {
  const parentRef = useRef<HTMLDivElement | null>(null);
  const shouldRenderSections = metric === "rating" && !!previousTopKeys && !!currentTopKeys;
  // rating-detail: no virtualization (render all, no scroll container)
  const shouldVirtualize = !shouldRenderSections && presentation !== "rating-detail" && entries.length >= 50;
  const colSpan = 9;
  const valueLabel = metric === "exp" ? "경험치" : "레이팅";
  // rating-detail uses same column layout as default
  const columns = presentation === "day-detail" ? DAY_DETAIL_COLUMNS : DEFAULT_COLUMNS;

  const sortedEntries = useMemo(() => {
    if (!allowSort || entries.length <= 1) return entries;
    return [...entries].sort((left, right) => compareEntries(left, right, sortBy, sortDir));
  }, [allowSort, entries, sortBy, sortDir]);

  const sectionModels = useMemo<SectionModel[] | null>(() => {
    if (!shouldRenderSections || !previousTopKeys || !currentTopKeys) return null;

    const buckets: Record<SectionKey, RankingContributionEntry[]> = {
      kept: [],
      entered: [],
      dropped: [],
    };
    const deltaTotals: Record<SectionKey, number> = {
      kept: 0,
      entered: 0,
      dropped: 0,
    };

    for (const entry of entries) {
      const key = contributionKey(entry);
      const wasInTop = previousTopKeys.has(key);
      const isInTop = currentTopKeys.has(key);
      const section: SectionKey | null = wasInTop && isInTop
        ? "kept"
        : (!wasInTop && isInTop)
          ? "entered"
          : (wasInTop && !isInTop)
            ? "dropped"
            : null;

      if (!section) continue;
      buckets[section].push(entry);
      if (section === "kept" && entry.delta_rating != null) {
        deltaTotals[section] += entry.delta_rating;
      }
    }

    const orderedSections: SectionKey[] = ["entered", "kept", "dropped"];
    return orderedSections
      .map<SectionModel | null>((section) => {
        const bucket = [...buckets[section]].sort(
          (left, right) => sectionDisplayRank(left, section) - sectionDisplayRank(right, section),
        );
        if (bucket.length === 0) return null;

        const rows: SectionRow[] = [];
        let lastRank: number | null = null;
        for (const entry of bucket) {
          const displayRank = sectionDisplayRank(entry, section);
          const key = contributionKey(entry);
          if (lastRank == null) {
            if (displayRank > 1) {
              rows.push({ kind: "ellipsis", id: `${section}-top-gap` });
            }
          } else if (displayRank - lastRank > 1) {
            rows.push({ kind: "ellipsis", id: `${section}-${lastRank}-${displayRank}-gap` });
          }
          rows.push({ kind: "entry", id: key, entry });
          lastRank = displayRank;
        }
        if (lastRank != null && lastRank < totalEntries) {
          rows.push({ kind: "ellipsis", id: `${section}-bottom-gap` });
        }
        return {
          section,
          count: bucket.length,
          averageDelta: section === "kept" ? deltaTotals[section] / bucket.length : null,
          rows,
        };
      })
      .filter((model): model is SectionModel => model !== null);
  }, [currentTopKeys, entries, previousTopKeys, shouldRenderSections, totalEntries]);

  // eslint-disable-next-line react-hooks/incompatible-library
  const rowVirtualizer = useVirtualizer({
    count: shouldVirtualize ? sortedEntries.length : 0,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
  });

  useEffect(() => {
    parentRef.current?.scrollTo({ top: 0 });
  }, [metric, sortBy, sortDir, entries, sectionModels]);

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 8 }).map((_, index) => (
          <div key={index} className="h-14 animate-pulse rounded-lg bg-secondary/50" />
        ))}
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card/50 px-6 py-12 text-center text-body text-muted-foreground">
        {emptyMessage}
      </div>
    );
  }

  if (sectionModels) {
    const sectionMaxHeight = presentation === "rating-detail" ? undefined : MAX_TABLE_HEIGHT;
    return (
      <div
        ref={parentRef}
        className="space-y-3 overflow-auto pr-1"
        style={sectionMaxHeight !== undefined ? { maxHeight: sectionMaxHeight } : undefined}
      >
        {sectionModels.map((section) => (
          <SectionCard
            key={section.section}
            section={section.section}
            rows={section.rows}
            count={section.count}
            averageDelta={section.averageDelta}
            colSpan={colSpan}
            topN={topN}
            valueLabel={valueLabel}
            presentation={presentation}
            userId={userId}
          />
        ))}
      </div>
    );
  }

  const virtualRows = rowVirtualizer.getVirtualItems();
  const totalSize = rowVirtualizer.getTotalSize();
  const paddingTop = shouldVirtualize && virtualRows.length > 0 ? virtualRows[0]?.start ?? 0 : 0;
  const paddingBottom = shouldVirtualize && virtualRows.length > 0
    ? totalSize - (virtualRows[virtualRows.length - 1]?.end ?? 0)
    : 0;
  const renderedEntries = shouldVirtualize
    ? virtualRows.map((virtualRow) => sortedEntries[virtualRow.index])
    : sortedEntries;

  // rating-detail: no max height — render all rows without scroll
  const tableMaxHeight = presentation === "rating-detail" ? undefined : MAX_TABLE_HEIGHT;

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card/60">
      <div
        ref={parentRef}
        className="overflow-auto"
        style={tableMaxHeight !== undefined ? { maxHeight: tableMaxHeight } : undefined}
      >
        <table className="w-full border-collapse" style={{ tableLayout: "fixed", minWidth: 960 }}>
          <colgroup>
            {columns.map((column, index) => (
              <col key={index} style={column.width ? { width: column.width } : undefined} />
            ))}
          </colgroup>
          <TableHeader
            allowSort={allowSort}
            sortBy={sortBy}
            sortDir={sortDir}
            onSortChange={onSortChange}
            valueLabel={valueLabel}
            columns={columns}
          />
          <tbody>
            {shouldVirtualize && paddingTop > 0 && (
              <tr><td colSpan={colSpan} style={{ height: paddingTop, padding: 0, border: 0 }} /></tr>
            )}
            {renderedEntries.map((entry) => (
              <ContributionRow
                key={contributionKey(entry)}
                entry={entry}
                metric={metric}
                presentation={presentation}
                columns={columns}
                userId={userId}
              />
            ))}
            {shouldVirtualize && paddingBottom > 0 && (
              <tr><td colSpan={colSpan} style={{ height: paddingBottom, padding: 0, border: 0 }} /></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
