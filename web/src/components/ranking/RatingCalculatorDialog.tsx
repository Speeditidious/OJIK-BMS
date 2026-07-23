"use client";

import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronLeft, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { TableLevelBadges } from "@/components/common/TableLevelBadges";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
  CLEAR_TYPE_LABELS,
  LR2_CLEAR_TYPE_LABELS,
  BEATORAJA_CLEAR_TYPE_LABELS,
} from "@/components/charts/ClearDistributionChart";
import { useRatingCalcParams } from "@/hooks/use-rating-calc";
import { usePlaySummary } from "@/hooks/use-analysis";
import { useRankingContributionRows } from "@/hooks/use-rankings";
import type { GoalDraft } from "@/lib/goal-types";
import { CLEAR_ROW_STATIC_CLASS } from "@/lib/fumen-table-utils";
import { validateGoalTarget } from "@/lib/goal-validation-core.mjs";
import { formatGoalValidationErrors } from "@/lib/goal-validation-message";
import {
  lampName,
  RANK_ORDER,
  resolveLevel,
  songRating,
} from "@/lib/rating-calc-core.mjs";
import { formatRatePercent } from "@/lib/rate-format";
import { songHref } from "@/lib/song-href";
import { formatTableLevelWithSymbolForDisplay } from "@/lib/table-level-display";
import { cn } from "@/lib/utils";

/**
 * Clear types offered in the adjustable select, in display order. The UI keeps
 * every user-facing lamp available even when multiple lamps share the same
 * rating multiplier, because goals are about the exact play result as well as
 * the derived rating.
 */
export const RATING_CLEAR_TYPES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];
export const LR2_RATING_CLEAR_TYPES = [0, 1, 3, 4, 5, 7, 8, 9];
export const RATING_RANKS = RANK_ORDER;
export const RANK_MIN_RATES: Record<string, number> = {
  F: 0,
  E: (2 / 9) * 100,
  D: (3 / 9) * 100,
  C: (4 / 9) * 100,
  B: (5 / 9) * 100,
  A: (6 / 9) * 100,
  AA: (7 / 9) * 100,
  AAA: (8 / 9) * 100,
  "MAX-": (8.5 / 9) * 100,
  MAX: 100,
};

/**
 * Keep raw clear_type values as-is for the editable row. NOPLAY / no-record
 * falls back to FAILED so opening an unplayed chart immediately models a real
 * play result and can be saved as a goal.
 */
export function normalizeClearForRating(clearType: number | null): number {
  if (clearType == null || clearType === 0) return 1;
  return Math.min(9, Math.max(0, Math.trunc(clearType)));
}

/**
 * Derive the DJ rank grade from a rate (%). Thresholds per
 * `documents/bms_score_formula.md` (common LR2/Beatoraja rank calc). Used only
 * for the *adjusted* row when the user changes rate; an unchanged rate keeps
 * the record's actual server-provided grade.
 */
export function rankGradeFromRate(rate: number | null): string {
  if (rate == null) return "F";
  if (rate >= 100) return "MAX";
  if (rate >= (8.5 / 9) * 100) return "MAX-";
  if (rate >= (8 / 9) * 100) return "AAA";
  if (rate >= (7 / 9) * 100) return "AA";
  if (rate >= (6 / 9) * 100) return "A";
  if (rate >= (5 / 9) * 100) return "B";
  if (rate >= (4 / 9) * 100) return "C";
  if (rate >= (3 / 9) * 100) return "D";
  if (rate >= (2 / 9) * 100) return "E";
  return "F";
}

export function minRateForRank(rank: string): number {
  return Math.round((RANK_MIN_RATES[rank] ?? 0) * 100) / 100;
}

/** Same 3-line client -> label-set dispatch as RecentActivity.tsx's local (unexported) `getClientLabels`. */
export function getClientLabels(clientType: string) {
  if (clientType === "lr2") return LR2_CLEAR_TYPE_LABELS;
  if (clientType === "beatoraja") return BEATORAJA_CLEAR_TYPE_LABELS;
  return CLEAR_TYPE_LABELS;
}

export interface RatingCalculatorDialogProps {
  open: boolean;
  onClose: () => void;
  tableSlug: string;
  fumen: {
    sha256: string | null;
    md5: string | null;
    level: string;
    title: string;
    artist: string | null;
    symbol?: string;
    levels?: Array<{ symbol: string; level: string; slug?: string }>;
  };
  ratingTableOptions?: Array<{ slug: string; displayName: string; level: string; symbol: string }>;
  current: {
    /** Raw clear_type integer 0-9. `null` = NOPLAY / no record. */
    clearType: number | null;
    /** e.g. "AA". `null` = no record. */
    rank: string | null;
    minBp: number | null;
    /** Raw 0-100. `null` = no record. */
    rate: number | null;
  };
  /**
   * Which client's record `current` represents; used to pick the clear-type
   * label set (LR2 vs Beatoraja differ) and passed through untouched to
   * `onSetGoal`.
   */
  clientType?: string;
  /** Profile owner whose table ranking the position column is computed against. */
  userId?: string | null;
  /** Hide the "set as goal" action when true (e.g. viewing another user's dashboard). */
  readonlyMode?: boolean;
  /** Overrides the dialog title (e.g. "목표 설정" when opened from the goal-setup wizard instead of a standalone calculator entry point). */
  titleOverride?: string;
  showBackButton?: boolean;
  onBack?: () => void;
  onSetGoal?: (draft: GoalDraft) => void;
}

function formatSongRatingValue(value: number): string {
  return Math.round(value).toLocaleString();
}

export const MAX_TARGET_BP = 2_147_483_647;

export function sanitizeBpInput(raw: string, currentMinBp: number | null): number | null {
  const trimmed = raw.trim();
  if (trimmed === "") return currentMinBp ?? null;
  const next = Number(trimmed);
  if (!Number.isFinite(next)) return currentMinBp ?? null;
  const normalized = Math.min(MAX_TARGET_BP, Math.max(0, Math.trunc(next)));
  if (currentMinBp != null && normalized > currentMinBp) return currentMinBp;
  return normalized;
}

export function sanitizeRateInput(raw: string, currentRate: number | null): number | null {
  const trimmed = raw.trim();
  if (trimmed === "") return currentRate ?? null;
  const next = Number(trimmed);
  if (!Number.isFinite(next)) return currentRate ?? null;
  if (next < 0 || next > 100) return currentRate;
  return Math.round(next * 100) / 100;
}

function currentClearForAdjustedClient(clearType: number | null, adjustedClientType: string): number {
  const raw = clearType ?? 0;
  if (adjustedClientType === "lr2") {
    if (raw === 2) return 1;
    if (raw === 6) return 5;
  }
  return Math.min(9, Math.max(0, Math.trunc(raw)));
}

function resolveMostRecentClientType(
  lr2SyncedAt: string | null | undefined,
  beatorajaSyncedAt: string | null | undefined,
  fallback: string | null | undefined,
): string {
  if (lr2SyncedAt && beatorajaSyncedAt) {
    const lr2Time = new Date(lr2SyncedAt).getTime();
    const beatorajaTime = new Date(beatorajaSyncedAt).getTime();
    if (Number.isFinite(lr2Time) && Number.isFinite(beatorajaTime) && beatorajaTime > lr2Time) {
      return "beatoraja";
    }
    return "lr2";
  }
  if (lr2SyncedAt) return "lr2";
  if (beatorajaSyncedAt) return "beatoraja";
  return fallback === "lr2" || fallback === "beatoraja" ? fallback : "lr2";
}

interface CalcResult {
  virtualSongRating: number | null;
  /** null when there's no real current record (NOPLAY) — there's nothing to rate. */
  currentSongRating: number | null;
  /** 1-based positions within the table's rating ranking, or null if rows unavailable / no current record. */
  currentPosition: number | null;
  adjustedPosition: number | null;
}

const GRID_TEMPLATE = "grid-cols-[64px_minmax(96px,0.8fr)_minmax(132px,1fr)_104px_116px_72px_minmax(0,1.2fr)]";

/** Column header cell. `emphasis` matches the rating-detail table's bold value header. */
function ResetHeaderButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onClick}
          className="inline-flex h-5 w-5 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          aria-label={label}
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </button>
      </TooltipTrigger>
      <TooltipContent className="text-label">{label}</TooltipContent>
    </Tooltip>
  );
}

function HeaderCell({
  children,
  emphasis,
  resetLabel,
  onReset,
}: {
  children: React.ReactNode;
  emphasis?: boolean;
  resetLabel?: string;
  onReset?: () => void;
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-center gap-1 px-2 py-2",
        emphasis ? "text-base font-bold text-foreground" : "text-label font-medium text-muted-foreground",
      )}
    >
      {children}
      {onReset && resetLabel && <ResetHeaderButton label={resetLabel} onClick={onReset} />}
    </div>
  );
}

/** Body cell wrapper — centered, consistent padding. */
function Cell({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex min-w-0 items-center justify-center px-2 py-3", className)}>
      {children}
    </div>
  );
}

function RatingLevelDisplay({
  levels,
  levelDisplay,
  className,
}: {
  levels?: Array<{ symbol: string; level: string; slug?: string }>;
  levelDisplay: string | null;
  className?: string;
}) {
  const filtered = (levels ?? []).filter((level) => level.level);
  if (filtered.length > 0) {
    return (
      <span className={cn("flex flex-wrap items-center justify-center gap-1", className)}>
        {filtered.map((level) => (
          <span
            key={`${level.symbol}-${level.level}`}
            className="rounded-md border border-primary/40 bg-primary/10 px-1.5 py-0.5 text-caption font-semibold text-primary"
          >
            {formatTableLevelWithSymbolForDisplay({ tableSymbol: level.symbol, level: level.level })}
          </span>
        ))}
      </span>
    );
  }
  if (!levelDisplay) return null;
  return <span className={className}>{levelDisplay}</span>;
}

function RatingLevelTableCell({
  levels,
  levelDisplay,
}: {
  levels?: Array<{ symbol: string; level: string; slug?: string }>;
  levelDisplay: string | null;
}) {
  const filtered = (levels ?? []).filter((level) => level.level);
  if (filtered.length > 0) {
    return <TableLevelBadges levels={filtered.map((level) => ({ ...level, slug: level.slug ?? "" }))} maxVisible={2} />;
  }
  return <span className="text-label font-semibold tabular-nums">{levelDisplay ?? "—"}</span>;
}

/** The shared column-header row, repeated by both the current and adjusted tables. */
function ColumnHeaderRow({
  t,
  resets,
  ratingTableOptions,
  selectedRatingTableSlug,
  onRatingTableChange,
}: {
  t: (key: string) => string;
  resets?: Partial<Record<"clear" | "bp" | "rate" | "rank", () => void>>;
  ratingTableOptions?: Array<{ slug: string; displayName: string; level: string; symbol: string }>;
  selectedRatingTableSlug?: string;
  onRatingTableChange?: (slug: string) => void;
}) {
  const canSelectRatingTable = (ratingTableOptions?.length ?? 0) > 1 && selectedRatingTableSlug && onRatingTableChange;
  return (
    <div className={cn("grid border-b border-border", GRID_TEMPLATE)}>
      <HeaderCell>{t("ranking.rank")}</HeaderCell>
      <HeaderCell>{t("common.fields.level")}</HeaderCell>
      <HeaderCell resetLabel={t("ranking.detail.calculator.resetClear")} onReset={resets?.clear}>
        {t("common.fields.clear")}
      </HeaderCell>
      <HeaderCell resetLabel={t("ranking.detail.calculator.resetBp")} onReset={resets?.bp}>
        BP
      </HeaderCell>
      <HeaderCell resetLabel={t("ranking.detail.calculator.resetRate")} onReset={resets?.rate}>
        {t("common.fields.rate")}
      </HeaderCell>
      <HeaderCell resetLabel={t("ranking.detail.calculator.resetRank")} onReset={resets?.rank}>
        {t("common.fields.rank")}
      </HeaderCell>
      <HeaderCell emphasis>
        <span>{t("ranking.rating")}</span>
        {canSelectRatingTable && (
          <Select value={selectedRatingTableSlug} onValueChange={onRatingTableChange}>
            <SelectTrigger
              aria-label={t("goals.setup.chooseRatingTable")}
              className="ml-1 h-7 w-7 border-border bg-card px-1 shadow-none"
            >
              <span className="sr-only">
                <SelectValue />
              </span>
            </SelectTrigger>
            <SelectContent align="end" className="min-w-52">
              {ratingTableOptions!.map((option) => (
                <SelectItem key={option.slug} value={option.slug}>
                  <span className="flex items-center gap-2">
                    <span className="rounded-md border border-primary/40 bg-primary/10 px-1.5 py-0.5 text-caption font-semibold text-primary">
                      {formatTableLevelWithSymbolForDisplay({ tableSymbol: option.symbol, level: option.level })}
                    </span>
                    <span>{option.displayName}</span>
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </HeaderCell>
    </div>
  );
}

/** Section title strip carrying the "current" / "adjusted" label for each table. */
function SectionTitle({ label, accent, children }: { label: string; accent?: boolean; children?: ReactNode }) {
  return (
    <div className="flex min-h-10 items-center gap-3 border-b border-border/50 bg-secondary/40 px-4 py-2">
      <span className={cn("text-caption font-semibold", accent ? "text-primary" : "text-muted-foreground")}>
        {label}
      </span>
      {children}
    </div>
  );
}

/**
 * "What-if" rating calculator popup. Renders the chart as two stacked
 * tables — a read-only "current" table and an editable "adjusted" table,
 * each carrying its own title and the rating-detail column layout. The
 * adjusted table's clear-lamp / BP / rate cells are editable; rank grade
 * derives from rate, and the adjusted rating + position update immediately,
 * computed client-side from the table's calc params (only calc-params +
 * contribution rows fetched on open, no per-keystroke server round-trip).
 *
 * Opened from a rating-detail table cell, a day-stat-sheet card, and (in goal
 * mode) the goal-setup flow.
 */
export function RatingCalculatorDialog({
  open,
  onClose,
  tableSlug,
  fumen,
  ratingTableOptions,
  current,
  clientType,
  userId,
  readonlyMode = false,
  titleOverride,
  showBackButton = false,
  onBack,
  onSetGoal,
}: RatingCalculatorDialogProps) {
  const { t } = useTranslation();

  // Adjustable control state, reset from `current` whenever the dialog is (re)opened for a (possibly new) fumen —
  // mirrors AnnouncementEditorDialog.tsx's open-triggered reset useEffect. Clear is normalized onto a
  // selectable rating-equivalent lamp so the editable row starts at zero delta.
  const [clearType, setClearType] = useState<number>(() => normalizeClearForRating(current.clearType));
  const [minBp, setMinBp] = useState<number | null>(current.minBp);
  const [rate, setRate] = useState<number | null>(current.rate);
  const [adjustedRank, setAdjustedRank] = useState<string>(current.rank ?? rankGradeFromRate(current.rate));
  const [adjustedClientType, setAdjustedClientType] = useState<string>(clientType ?? "lr2");
  const [rateEditing, setRateEditing] = useState(false);
  const [selectedRatingTableSlug, setSelectedRatingTableSlug] = useState(tableSlug);
  const userPickedClientRef = useRef(false);
  const lr2Summary = usePlaySummary("lr2", userId ?? undefined, open && !!userId);
  const beatorajaSummary = usePlaySummary("beatoraja", userId ?? undefined, open && !!userId);

  const preferredClientType = useMemo(
    () =>
      resolveMostRecentClientType(
        lr2Summary.data?.last_synced_at,
        beatorajaSummary.data?.last_synced_at,
        clientType,
      ),
    [lr2Summary.data?.last_synced_at, beatorajaSummary.data?.last_synced_at, clientType],
  );

  useEffect(() => {
    if (open) {
      setClearType(normalizeClearForRating(current.clearType));
      setMinBp(current.minBp);
      setRate(current.rate);
      setAdjustedRank(current.rank ?? rankGradeFromRate(current.rate));
      setAdjustedClientType(preferredClientType);
      setSelectedRatingTableSlug(tableSlug);
      setRateEditing(false);
      userPickedClientRef.current = false;
    }
    // Only reset on open/fumen-identity change, not on every `current` object identity change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, fumen.sha256, fumen.md5]);

  useEffect(() => {
    if (!open || userPickedClientRef.current) return;
    setAdjustedClientType(preferredClientType);
  }, [open, preferredClientType]);

  const effectiveTableSlug = selectedRatingTableSlug || tableSlug;
  const selectedRatingTable = ratingTableOptions?.find((option) => option.slug === effectiveTableSlug) ?? null;
  const effectiveFumen = selectedRatingTable
    ? { ...fumen, level: selectedRatingTable.level, symbol: selectedRatingTable.symbol }
    : fumen;

  const calcParamsQuery = useRatingCalcParams(open && effectiveTableSlug ? effectiveTableSlug : null);
  const contributionQuery = useRankingContributionRows({
    tableSlug: effectiveTableSlug,
    metric: "rating",
    scope: "all",
    sortBy: "value",
    sortDir: "desc",
    userId: userId ?? undefined,
    enabled: open && !!effectiveTableSlug,
  });
  const config = calcParamsQuery.data?.config ?? null;
  const isInitialLoading = calcParamsQuery.isLoading;

  const effectiveCurrentClearType = current.clearType ?? 0;
  const currentClearLabels = getClientLabels(clientType ?? "");
  const adjustedClearLabels = getClientLabels(adjustedClientType);
  const adjustedClearTypes = adjustedClientType === "lr2" ? LR2_RATING_CLEAR_TYPES : RATING_CLEAR_TYPES;

  const rateChanged = (rate ?? null) !== (current.rate ?? null);
  const rankChanged = (adjustedRank ?? null) !== (current.rank ?? rankGradeFromRate(current.rate));

  function updateClearType(nextClearType: number) {
    const normalized = adjustedClientType === "lr2" && nextClearType === 2
      ? 1
      : adjustedClientType === "lr2" && nextClearType === 6
        ? 5
        : nextClearType;
    setClearType(normalized);
    if (normalized === 9) {
      setRate(100);
      setAdjustedRank("MAX");
    }
  }

  function updateRate(nextRate: number | null) {
    setRate(nextRate);
    if (nextRate === 100) {
      setClearType(9);
      setAdjustedRank("MAX");
    } else {
      setAdjustedRank(rankGradeFromRate(nextRate));
    }
  }

  function updateRank(nextRank: string) {
    setAdjustedRank(nextRank);
    const nextRate = minRateForRank(nextRank);
    setRate(nextRate);
    if (nextRank === "MAX") {
      setClearType(9);
    }
  }

  function resetClear() {
    updateClearType(currentClearForAdjustedClient(current.clearType, adjustedClientType));
  }

  function resetBp() {
    setMinBp(current.minBp);
  }

  function resetRateAndRank() {
    const nextRate = current.rate;
    setRate(nextRate);
    if (nextRate === 100 || current.rank === "MAX") {
      setClearType(9);
      setAdjustedRank("MAX");
      return;
    }
    setAdjustedRank(current.rank ?? rankGradeFromRate(nextRate));
  }

  const calcResult = useMemo<CalcResult | null>(() => {
    if (!config) {
      return {
        virtualSongRating: null,
        currentSongRating: null,
        currentPosition: null,
        adjustedPosition: null,
      };
    }

    const virtualLamp = lampName(clearType);
    const currentLamp = lampName(current.clearType);
    const virtualLevel = resolveLevel(effectiveFumen.sha256, effectiveFumen.md5, virtualLamp, effectiveFumen.level, config);
    const virtualSongRating = songRating(
      { level: virtualLevel, lamp: virtualLamp, rank: adjustedRank, bp: minBp, rate },
      config,
    );

    // NOPLAY has no real record — songRating() would return 0.0 for it, which reads as a
    // genuine (if low) rating rather than "not applicable." Keep currentSongRating/currentPosition
    // null in that case so the UI shows "-" instead of a fabricated number.
    let currentSongRating: number | null = null;
    if (currentLamp !== "NOPLAY") {
      const currentResolvedLevel = resolveLevel(effectiveFumen.sha256, effectiveFumen.md5, currentLamp, effectiveFumen.level, config);
      currentSongRating = songRating(
        {
          level: currentResolvedLevel,
          lamp: currentLamp,
          rank: current.rank ?? "F",
          bp: current.minBp,
          rate: current.rate,
        },
        config,
      );
    }

    // Position = 1 + (# of *other* charts rated strictly higher). Exclude this fumen's own row so the
    // adjusted rating replaces (not double-counts) it.
    let currentPosition: number | null = null;
    let adjustedPosition: number | null = null;
    const entries = contributionQuery.data?.entries;
    if (entries) {
      const otherValues = entries
        .filter(
          (entry) =>
            !(
              (effectiveFumen.sha256 != null && entry.sha256 === effectiveFumen.sha256) ||
              (effectiveFumen.md5 != null && entry.md5 === effectiveFumen.md5)
            ),
        )
        .map((entry) => entry.value);
      const positionFor = (rating: number) =>
        1 + otherValues.reduce((count, value) => (value > rating ? count + 1 : count), 0);
      if (currentSongRating != null) currentPosition = positionFor(currentSongRating);
      adjustedPosition = positionFor(virtualSongRating);
    }

    return { virtualSongRating, currentSongRating, currentPosition, adjustedPosition };
  }, [
    config,
    clearType,
    adjustedRank,
    minBp,
    rate,
    current.clearType,
    current.rank,
    current.minBp,
    current.rate,
    effectiveFumen.sha256,
    effectiveFumen.md5,
    effectiveFumen.level,
    contributionQuery.data,
  ]);

  // Only fields the user actually changed from `current` become goal conditions — see Task 7:
  // "just get HARD" shouldn't also demand an unrelated exact BP/rate match.
  const clearChanged = clearType !== (current.clearType ?? 0);
  const bpChanged = (minBp ?? null) !== (current.minBp ?? null);
  const hasAnyChange = clearChanged || bpChanged || rateChanged || rankChanged;

  const goalTarget = useMemo(
    () => ({
      clearType: clearChanged ? clearType : null,
      minBp: bpChanged ? minBp : null,
      rate: rateChanged ? rate : null,
      rank: rankChanged ? adjustedRank : null,
    }),
    [clearChanged, clearType, bpChanged, minBp, rateChanged, rate, rankChanged, adjustedRank],
  );

  const goalValidation = useMemo(
    () =>
      validateGoalTarget(
        { clear_type: current.clearType, min_bp: current.minBp, rank: current.rank, rate: current.rate },
        goalTarget,
      ),
    [current.clearType, current.minBp, current.rank, current.rate, goalTarget],
  );

  const songUrl = effectiveFumen.sha256 || effectiveFumen.md5 ? songHref({ sha256: effectiveFumen.sha256, md5: effectiveFumen.md5 }) : null;
  const levelDisplay = effectiveFumen.level
    ? formatTableLevelWithSymbolForDisplay({ tableSymbol: effectiveFumen.symbol, level: effectiveFumen.level })
    : null;

  function handleSetGoal() {
    if (!onSetGoal || !hasAnyChange || !goalValidation.ok) return;
    onSetGoal({
      tableSlug: effectiveTableSlug,
      fumen: effectiveFumen,
      clientType: adjustedClientType,
      clearType: goalTarget.clearType,
      rank: goalTarget.rank,
      minBp: goalTarget.minBp,
      rate: goalTarget.rate,
      projectedRating: calcResult?.virtualSongRating ?? null,
    });
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden bg-card p-0">
        <DialogHeader className="border-b border-border px-6 py-4">
          {showBackButton && (
            <Button variant="ghost" size="sm" className="mb-2 h-9 shrink-0 self-start justify-start gap-1 rounded-md text-muted-foreground" onClick={onBack ?? onClose}>
              <ChevronLeft className="h-4 w-4" />
              {t("common.actions.back")}
            </Button>
          )}
          <DialogTitle className="text-lg font-semibold">
            {titleOverride ?? t("ranking.detail.calculator.title")}
          </DialogTitle>
          <div className="mt-1 flex items-center gap-2">
            {effectiveFumen.levels?.filter((level) => level.level).length ? (
              <span className="shrink-0">
                <RatingLevelDisplay levels={effectiveFumen.levels} levelDisplay={levelDisplay} />
              </span>
            ) : levelDisplay ? (
              <span className="shrink-0 rounded-md border border-primary/40 bg-primary/10 px-2 py-0.5 text-caption font-semibold text-primary">
                {levelDisplay}
              </span>
            ) : null}
            <div className="min-w-0">
              {songUrl ? (
                <a
                  href={songUrl}
                  className="block truncate text-body font-semibold transition-colors hover:text-primary"
                >
                  {effectiveFumen.title}
                </a>
              ) : (
                <span className="block truncate text-body font-semibold">{effectiveFumen.title}</span>
              )}
              {effectiveFumen.artist && (
                <div className="truncate text-caption text-muted-foreground">{effectiveFumen.artist}</div>
              )}
            </div>
          </div>
        </DialogHeader>

        <TooltipProvider delayDuration={150}>
        <div className="flex-1 space-y-3 overflow-y-auto px-6 py-5">
          {/* Current table (read-only) */}
          <div className="overflow-hidden rounded-xl border border-border bg-card/60">
            <SectionTitle label={t("ranking.detail.calculator.current")} />
            <ColumnHeaderRow
              t={t}
              ratingTableOptions={ratingTableOptions}
              selectedRatingTableSlug={effectiveTableSlug}
              onRatingTableChange={setSelectedRatingTableSlug}
            />
            <div className={cn("grid items-stretch", GRID_TEMPLATE, CLEAR_ROW_STATIC_CLASS[effectiveCurrentClearType])}>
              <Cell>
                {calcResult?.currentPosition != null ? (
                  <span className="text-label font-semibold tabular-nums">{calcResult.currentPosition}</span>
                ) : (
                  <span className="text-label text-muted-foreground">—</span>
                )}
              </Cell>
              <Cell>
                <RatingLevelTableCell levels={effectiveFumen.levels} levelDisplay={levelDisplay} />
              </Cell>
              <Cell>
                <span className="text-label font-semibold">
                  {currentClearLabels[effectiveCurrentClearType] ?? CLEAR_TYPE_LABELS[effectiveCurrentClearType] ?? String(effectiveCurrentClearType)}
                </span>
              </Cell>
              <Cell>
                <span className="text-label tabular-nums">{current.minBp ?? "—"}</span>
              </Cell>
              <Cell>
                <span className="text-label tabular-nums">
                  {current.rate != null ? formatRatePercent(current.rate) : "—"}
                </span>
              </Cell>
              <Cell>
                <span className="text-label font-semibold">{current.rank ?? "—"}</span>
              </Cell>
              <Cell className="rating-value-cell text-base font-bold tabular-nums">
                {isInitialLoading ? (
                  <Skeleton className="h-5 w-20" />
                ) : calcResult?.currentSongRating != null ? (
                  formatSongRatingValue(calcResult.currentSongRating)
                ) : (
                  "—"
                )}
              </Cell>
            </div>
          </div>

          {/* Adjusted table (editable) */}
          <div className="overflow-hidden rounded-xl border border-border bg-card/60">
            <SectionTitle label={t("ranking.detail.calculator.adjusted")} accent>
              <div className="ml-auto flex items-center gap-1">
                {(["lr2", "beatoraja"] as const).map((ct) => (
                  <button
                    key={ct}
                    type="button"
                    onClick={() => {
                      setAdjustedClientType(ct);
                      userPickedClientRef.current = true;
                      if (ct === "lr2" && (clearType === 2 || clearType === 6)) {
                        setClearType(clearType === 2 ? 1 : 5);
                      }
                    }}
                    className={cn(
                      "rounded-md border px-2 py-1 text-caption font-semibold transition-colors",
                      adjustedClientType === ct
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border bg-card text-muted-foreground hover:border-primary/50",
                    )}
                  >
                    {ct === "lr2" ? "LR2" : "Beatoraja"}
                  </button>
                ))}
              </div>
            </SectionTitle>
            <ColumnHeaderRow
              t={t}
              resets={{ clear: resetClear, bp: resetBp, rate: resetRateAndRank, rank: resetRateAndRank }}
              ratingTableOptions={ratingTableOptions}
              selectedRatingTableSlug={effectiveTableSlug}
              onRatingTableChange={setSelectedRatingTableSlug}
            />
            <div className={cn("grid items-stretch", GRID_TEMPLATE, CLEAR_ROW_STATIC_CLASS[clearType])}>
              <Cell>
                {calcResult?.adjustedPosition != null ? (
                  <span className="text-label font-semibold tabular-nums">{calcResult.adjustedPosition}</span>
                ) : (
                  <span className="text-label text-muted-foreground">—</span>
                )}
              </Cell>
              <Cell>
                <RatingLevelTableCell levels={effectiveFumen.levels} levelDisplay={levelDisplay} />
              </Cell>
              <Cell>
                <div className="flex w-full max-w-[140px] flex-col items-center gap-1">
                  <select
                    value={clearType}
                    onChange={(e) => updateClearType(Number(e.target.value))}
                    aria-label={t("common.fields.clear")}
                    className="h-9 w-full cursor-pointer rounded-md border border-border bg-card px-2 text-center text-caption font-semibold text-foreground outline-none transition-colors focus:border-primary"
                  >
                    {adjustedClearTypes.map((ct) => (
                      <option key={ct} value={ct}>
                        {adjustedClearLabels[ct] ?? CLEAR_TYPE_LABELS[ct] ?? String(ct)}
                      </option>
                    ))}
                  </select>
                </div>
              </Cell>
              <Cell>
                <div className="flex w-full flex-col items-center gap-1">
                  <Input
                    type="text"
                    inputMode="numeric"
                    value={minBp ?? ""}
                    placeholder="-"
                    onChange={(e) => {
                      setMinBp(sanitizeBpInput(e.target.value, current.minBp));
                    }}
                    className="h-9 w-full px-1 text-center tabular-nums"
                  />
                </div>
              </Cell>
              <Cell>
                <div className="flex w-full flex-col items-center gap-1">
                  {rateEditing ? (
                    <Input
                      type="text"
                      inputMode="decimal"
                      autoFocus
                      value={rate ?? ""}
                      placeholder="-"
                      onBlur={() => setRateEditing(false)}
                      onChange={(e) => {
                        updateRate(sanitizeRateInput(e.target.value, current.rate));
                      }}
                      className="h-9 w-full px-1 text-center tabular-nums"
                    />
                  ) : (
                    <button
                      type="button"
                      onClick={() => setRateEditing(true)}
                      className="flex h-9 w-full items-center justify-center rounded-md border border-border bg-card px-1 text-center text-label tabular-nums outline-none transition-colors hover:border-primary/60"
                    >
                      {rate != null ? formatRatePercent(rate) : "—"}
                    </button>
                  )}
                </div>
              </Cell>
              <Cell>
                <select
                  value={adjustedRank}
                  onChange={(e) => updateRank(e.target.value)}
                  aria-label={t("common.fields.rank")}
                  className="h-9 w-full cursor-pointer rounded-md border border-border bg-card px-2 text-center text-caption font-semibold text-foreground outline-none transition-colors focus:border-primary"
                >
                  {RATING_RANKS.map((rank) => (
                    <option key={rank} value={rank}>
                      {rank}
                    </option>
                  ))}
                </select>
              </Cell>
              <Cell className="rating-value-cell text-base font-bold tabular-nums">
                {isInitialLoading ? (
                  <Skeleton className="h-5 w-20" />
                ) : calcResult?.virtualSongRating != null ? (
                  formatSongRatingValue(calcResult.virtualSongRating)
                ) : (
                  "—"
                )}
              </Cell>
            </div>
          </div>
        </div>
        </TooltipProvider>

        <DialogFooter className="flex-col items-stretch gap-2 border-t border-border px-6 py-3 sm:flex-row sm:items-center">
          {!readonlyMode && onSetGoal && hasAnyChange && !goalValidation.ok && (
            <p className="min-w-0 text-caption text-destructive sm:flex-1">
              {formatGoalValidationErrors(goalValidation.errors, t)}
            </p>
          )}
          <div className="ml-auto flex justify-end gap-2">
            {(!onSetGoal || readonlyMode) && (
              <Button variant="outline" onClick={onClose}>
                {t("common.actions.close")}
              </Button>
            )}
            {!readonlyMode && onSetGoal && (
              <Button onClick={handleSetGoal} disabled={!hasAnyChange || !goalValidation.ok}>
                {t("ranking.detail.calculator.setGoalButton")}
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
