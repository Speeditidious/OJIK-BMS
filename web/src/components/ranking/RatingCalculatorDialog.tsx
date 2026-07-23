"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  CLEAR_TYPE_LABELS,
  LR2_CLEAR_TYPE_LABELS,
  BEATORAJA_CLEAR_TYPE_LABELS,
} from "@/components/charts/ClearDistributionChart";
import { useRatingCalcParams } from "@/hooks/use-rating-calc";
import { useRankingContributionRows } from "@/hooks/use-rankings";
import type { GoalDraft } from "@/lib/goal-types";
import { CLEAR_ROW_STATIC_CLASS } from "@/lib/fumen-table-utils";
import {
  lampName,
  resolveLevel,
  songRating,
} from "@/lib/rating-calc-core.mjs";
import { formatRatePercent } from "@/lib/rate-format";
import { songHref } from "@/lib/song-href";
import { formatTableLevelWithSymbolForDisplay } from "@/lib/table-level-display";
import { cn } from "@/lib/utils";

/**
 * Clear types offered in the adjustable select, in display order. Restricted
 * to the *rating-distinct* lamps: the config's `base_lamp_mult` /
 * `upper_lamp_bonus` collapse ASSIST→FAILED, EXHARD→HARD and PERFECT/MAX→FC,
 * so those extra lamps never change the rating and are omitted. NOPLAY is not
 * selectable (a what-if always models an actual clear).
 */
export const RATING_CLEAR_TYPES = [1, 3, 4, 5, 7];

/**
 * Collapse any raw clear_type onto its rating-equivalent representative in
 * `RATING_CLEAR_TYPES`, so opening the calculator on an EXHARD/PERFECT/MAX/
 * ASSIST record starts the editable row at the matching selectable lamp with
 * an identical rating. NOPLAY / no-record falls back to FAILED (the lowest
 * selectable lamp).
 */
export function normalizeClearForRating(clearType: number | null): number {
  if (clearType == null || clearType === 0 || clearType === 2) return 1; // NOPLAY / no record / ASSIST → FAILED
  if (clearType === 6) return 5; // EXHARD → HARD
  if (clearType === 8 || clearType === 9) return 7; // PERFECT / MAX → FC
  return clearType; // 1, 3, 4, 5, 7 are already representative
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
  };
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
  onSetGoal?: (draft: GoalDraft) => void;
}

function formatSongRatingValue(value: number): string {
  return Math.round(value).toLocaleString();
}

interface CalcResult {
  virtualSongRating: number;
  /** null when there's no real current record (NOPLAY) — there's nothing to rate. */
  currentSongRating: number | null;
  /** 1-based positions within the table's rating ranking, or null if rows unavailable / no current record. */
  currentPosition: number | null;
  adjustedPosition: number | null;
}

const GRID_TEMPLATE = "grid-cols-[64px_56px_minmax(110px,1fr)_80px_100px_72px_minmax(0,1.2fr)]";

/** Column header cell. `emphasis` matches the rating-detail table's bold value header. */
function HeaderCell({ children, emphasis }: { children: React.ReactNode; emphasis?: boolean }) {
  return (
    <div
      className={cn(
        "flex items-center justify-center gap-1 px-2 py-2",
        emphasis ? "text-base font-bold text-foreground" : "text-label font-medium text-muted-foreground",
      )}
    >
      {children}
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

/** The shared column-header row, repeated by both the current and adjusted tables. */
function ColumnHeaderRow({ t }: { t: (key: string) => string }) {
  return (
    <div className={cn("grid border-b border-border", GRID_TEMPLATE)}>
      <HeaderCell>{t("ranking.rank")}</HeaderCell>
      <HeaderCell>{t("common.fields.level")}</HeaderCell>
      <HeaderCell>{t("common.fields.clear")}</HeaderCell>
      <HeaderCell>BP</HeaderCell>
      <HeaderCell>{t("common.fields.rate")}</HeaderCell>
      <HeaderCell>{t("common.fields.rank")}</HeaderCell>
      <HeaderCell emphasis>{t("ranking.rating")}</HeaderCell>
    </div>
  );
}

/** Section title strip carrying the "current" / "adjusted" label for each table. */
function SectionTitle({ label, accent }: { label: string; accent?: boolean }) {
  return (
    <div className="border-b border-border/50 bg-secondary/40 px-4 py-2">
      <span className={cn("text-caption font-semibold", accent ? "text-primary" : "text-muted-foreground")}>
        {label}
      </span>
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
  current,
  clientType,
  userId,
  readonlyMode = false,
  titleOverride,
  onSetGoal,
}: RatingCalculatorDialogProps) {
  const { t } = useTranslation();

  // Adjustable control state, reset from `current` whenever the dialog is (re)opened for a (possibly new) fumen —
  // mirrors AnnouncementEditorDialog.tsx's open-triggered reset useEffect. Clear is normalized onto a
  // selectable rating-equivalent lamp so the editable row starts at zero delta.
  const [clearType, setClearType] = useState<number>(() => normalizeClearForRating(current.clearType));
  const [minBp, setMinBp] = useState<number | null>(current.minBp);
  const [rate, setRate] = useState<number | null>(current.rate);

  useEffect(() => {
    if (open) {
      setClearType(normalizeClearForRating(current.clearType));
      setMinBp(current.minBp);
      setRate(current.rate);
    }
    // Only reset on open/fumen-identity change, not on every `current` object identity change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, fumen.sha256, fumen.md5]);

  const calcParamsQuery = useRatingCalcParams(open ? tableSlug : null);
  const contributionQuery = useRankingContributionRows({
    tableSlug,
    metric: "rating",
    scope: "all",
    sortBy: "value",
    sortDir: "desc",
    userId: userId ?? undefined,
    enabled: open,
  });
  const config = calcParamsQuery.data?.config ?? null;
  const isInitialLoading = calcParamsQuery.isLoading;

  const effectiveCurrentClearType = current.clearType ?? 0;
  const clearLabels = getClientLabels(clientType ?? "");

  const rateChanged = (rate ?? null) !== (current.rate ?? null);
  // Unchanged rate keeps the record's real grade; a changed rate re-derives it.
  const adjustedRank = rateChanged ? rankGradeFromRate(rate) : current.rank ?? rankGradeFromRate(rate);

  const calcResult = useMemo<CalcResult | null>(() => {
    if (!config) return null;

    const virtualLamp = lampName(clearType);
    const currentLamp = lampName(current.clearType);
    const virtualLevel = resolveLevel(fumen.sha256, fumen.md5, virtualLamp, fumen.level, config);
    const virtualSongRating = songRating(
      { level: virtualLevel, lamp: virtualLamp, rank: adjustedRank, bp: minBp, rate },
      config,
    );

    // NOPLAY has no real record — songRating() would return 0.0 for it, which reads as a
    // genuine (if low) rating rather than "not applicable." Keep currentSongRating/currentPosition
    // null in that case so the UI shows "-" instead of a fabricated number.
    let currentSongRating: number | null = null;
    if (currentLamp !== "NOPLAY") {
      const currentResolvedLevel = resolveLevel(fumen.sha256, fumen.md5, currentLamp, fumen.level, config);
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
              (fumen.sha256 != null && entry.sha256 === fumen.sha256) ||
              (fumen.md5 != null && entry.md5 === fumen.md5)
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
    fumen.sha256,
    fumen.md5,
    fumen.level,
    contributionQuery.data,
  ]);

  const songUrl = fumen.sha256 || fumen.md5 ? songHref({ sha256: fumen.sha256, md5: fumen.md5 }) : null;
  const levelDisplay = formatTableLevelWithSymbolForDisplay({ tableSymbol: fumen.symbol, level: fumen.level });

  function handleSetGoal() {
    if (!onSetGoal || !calcResult) return;
    onSetGoal({
      tableSlug,
      fumen,
      clientType: clientType ?? "",
      clearType,
      rank: adjustedRank,
      minBp,
      rate,
      projectedRating: calcResult.virtualSongRating,
    });
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden bg-card p-0">
        <DialogHeader className="border-b border-border px-6 py-4">
          <DialogTitle className="text-lg font-semibold">
            {titleOverride ?? t("ranking.detail.calculator.title")}
          </DialogTitle>
          <div className="mt-1 flex items-center gap-2">
            <span className="shrink-0 rounded-md border border-primary/40 bg-primary/10 px-2 py-0.5 text-caption font-semibold text-primary">
              {levelDisplay}
            </span>
            <div className="min-w-0">
              {songUrl ? (
                <a
                  href={songUrl}
                  className="block truncate text-body font-semibold transition-colors hover:text-primary"
                >
                  {fumen.title}
                </a>
              ) : (
                <span className="block truncate text-body font-semibold">{fumen.title}</span>
              )}
              {fumen.artist && (
                <div className="truncate text-caption text-muted-foreground">{fumen.artist}</div>
              )}
            </div>
          </div>
        </DialogHeader>

        <div className="flex-1 space-y-3 overflow-y-auto px-6 py-5">
          {/* Current table (read-only) */}
          <div className="overflow-hidden rounded-xl border border-border bg-card/60">
            <SectionTitle label={t("ranking.detail.calculator.current")} />
            <ColumnHeaderRow t={t} />
            <div className={cn("grid items-stretch", GRID_TEMPLATE, CLEAR_ROW_STATIC_CLASS[effectiveCurrentClearType])}>
              <Cell>
                {calcResult?.currentPosition != null ? (
                  <span className="text-label font-semibold tabular-nums">{calcResult.currentPosition}</span>
                ) : (
                  <span className="text-label text-muted-foreground">—</span>
                )}
              </Cell>
              <Cell>
                <span className="text-label font-semibold tabular-nums">{levelDisplay}</span>
              </Cell>
              <Cell>
                <span className="text-label font-semibold">
                  {clearLabels[effectiveCurrentClearType] ?? CLEAR_TYPE_LABELS[effectiveCurrentClearType] ?? String(effectiveCurrentClearType)}
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
            <SectionTitle label={t("ranking.detail.calculator.adjusted")} accent />
            <ColumnHeaderRow t={t} />
            <div className={cn("grid items-stretch", GRID_TEMPLATE, CLEAR_ROW_STATIC_CLASS[clearType])}>
              <Cell>
                {calcResult?.adjustedPosition != null ? (
                  <span className="text-label font-semibold tabular-nums">{calcResult.adjustedPosition}</span>
                ) : (
                  <span className="text-label text-muted-foreground">—</span>
                )}
              </Cell>
              <Cell>
                <span className="text-label font-semibold tabular-nums">{levelDisplay}</span>
              </Cell>
              <Cell>
                <select
                  value={clearType}
                  onChange={(e) => setClearType(Number(e.target.value))}
                  aria-label={t("common.fields.clear")}
                  className="h-9 w-full max-w-[140px] cursor-pointer rounded-md border border-border bg-card px-2 text-center text-caption font-semibold text-foreground outline-none transition-colors focus:border-primary"
                >
                  {RATING_CLEAR_TYPES.map((ct) => (
                    <option key={ct} value={ct}>
                      {clearLabels[ct] ?? CLEAR_TYPE_LABELS[ct] ?? String(ct)}
                    </option>
                  ))}
                </select>
              </Cell>
              <Cell>
                <Input
                  type="number"
                  min={0}
                  value={minBp ?? 0}
                  onChange={(e) => {
                    const next = Number(e.target.value);
                    setMinBp(Number.isFinite(next) ? Math.max(0, Math.trunc(next)) : 0);
                  }}
                  className="h-9 w-full px-1 text-center tabular-nums"
                />
              </Cell>
              <Cell>
                <div className="relative w-full">
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    step={0.01}
                    value={rate ?? 0}
                    onChange={(e) => {
                      const next = Number(e.target.value);
                      setRate(Number.isFinite(next) ? Math.min(100, Math.max(0, next)) : 0);
                    }}
                    className="h-9 w-full pl-1 pr-5 text-center tabular-nums"
                  />
                  <span className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 text-caption text-muted-foreground">
                    %
                  </span>
                </div>
              </Cell>
              <Cell>
                <span className="text-label font-semibold">{adjustedRank}</span>
              </Cell>
              <Cell className="rating-value-cell text-base font-bold tabular-nums">
                {isInitialLoading ? (
                  <Skeleton className="h-5 w-20" />
                ) : calcResult ? (
                  formatSongRatingValue(calcResult.virtualSongRating)
                ) : (
                  "—"
                )}
              </Cell>
            </div>
          </div>
        </div>

        <DialogFooter className="border-t border-border px-6 py-3">
          <Button variant="outline" onClick={onClose}>
            {t("common.actions.close")}
          </Button>
          {!readonlyMode && onSetGoal && (
            <Button onClick={handleSetGoal} disabled={!calcResult}>
              {t("ranking.detail.calculator.setGoalButton")}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
