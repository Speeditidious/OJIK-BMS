"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Info, Minus, Plus } from "lucide-react";
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
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { CLEAR_BADGE_STYLE } from "@/components/dashboard/RecentActivity";
import {
  CLEAR_TYPE_LABELS,
  LR2_CLEAR_TYPE_LABELS,
  BEATORAJA_CLEAR_TYPE_LABELS,
} from "@/components/charts/ClearDistributionChart";
import { useRatingCalcParams } from "@/hooks/use-rating-calc";
import { useMyRank, useRankingContributionRows } from "@/hooks/use-rankings";
import type { GoalDraft } from "@/lib/goal-types";
import {
  CLEAR_TYPE_TO_LAMP_NAME,
  RANK_ORDER,
  expLevel,
  lampName,
  resolveLevel,
  songRating,
  standardizeRating,
} from "@/lib/rating-calc-core.mjs";
import { formatRatePercent } from "@/lib/rate-format";
import { songHref } from "@/lib/song-href";
import { formatTableLevelWithSymbolForDisplay } from "@/lib/table-level-display";
import { cn } from "@/lib/utils";

/** FC-or-above clear_type integers — BP is ignored (forced to 0) by the formula at these lamps. */
const FC_OR_ABOVE_CLEAR_TYPES = new Set([7, 8, 9]);

/** Same 3-line client -> label-set dispatch as RecentActivity.tsx's local (unexported) `getClientLabels`. */
function getClientLabels(clientType: string) {
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
  /** Hide the "set as goal" action when true (e.g. viewing another user's dashboard). */
  readonlyMode?: boolean;
  onSetGoal?: (draft: GoalDraft) => void;
}

/** previous -> current value with an optional signed delta, matching ContributionTable.tsx's InlineComparison visual language. */
function ValueDelta({
  previous,
  current,
  diff,
}: {
  previous: React.ReactNode;
  current: React.ReactNode;
  diff?: React.ReactNode | null;
}) {
  return (
    <div className="inline-flex flex-wrap items-center gap-1.5 whitespace-nowrap">
      <span className="text-body opacity-70">{previous}</span>
      <span className="text-body opacity-70">→</span>
      <span className="text-h4 font-bold tabular-nums">{current}</span>
      {diff ? <span className="text-label font-bold tabular-nums opacity-75">{diff}</span> : null}
    </div>
  );
}

function formatSongRatingValue(value: number): string {
  return Math.round(value).toLocaleString();
}

function formatSongRatingDelta(delta: number): string | null {
  const rounded = Math.round(delta);
  if (rounded === 0) return null;
  return `${rounded > 0 ? "▲" : "▼"}${Math.abs(rounded).toLocaleString()}`;
}

function formatBmsforceValue(value: number): string {
  return value.toFixed(3);
}

function formatBmsforceDelta(delta: number): string | null {
  if (Math.abs(delta) < 0.0005) return null;
  return `${delta > 0 ? "▲" : "▼"}${Math.abs(delta).toFixed(3)}`;
}

type TotalImpactResult =
  | { status: "ok"; currentBmsForce: number; nextBmsForce: number }
  | { status: "unavailable"; reason: "pending" | "no_scores" | "error" };

interface CalcResult {
  virtualSongRating: number;
  currentSongRating: number;
  totalImpact: TotalImpactResult;
}

/**
 * "What-if" rating calculator popup. Lets the user adjust a chart's
 * clear-lamp / rank / BP / rate and immediately see the resulting per-chart
 * rating and the resulting change to their total table BMSFORCE, computed
 * entirely client-side (only 3 fetches on open, zero server round-trips per
 * keystroke).
 *
 * Standalone/reusable — has no wired entry point yet. Tasks 4/5/6 open this
 * from a rating-detail table cell, a day-stat-sheet card, and a
 * chart-picker search dialog respectively.
 */
export function RatingCalculatorDialog({
  open,
  onClose,
  tableSlug,
  fumen,
  current,
  clientType,
  readonlyMode = false,
  onSetGoal,
}: RatingCalculatorDialogProps) {
  const { t } = useTranslation();

  // Adjustable control state, reset from `current` whenever the dialog is (re)opened for a (possibly new) fumen —
  // mirrors AnnouncementEditorDialog.tsx's open-triggered reset useEffect.
  const [clearType, setClearType] = useState<number | null>(current.clearType);
  const [rank, setRank] = useState<string | null>(current.rank);
  const [minBp, setMinBp] = useState<number | null>(current.minBp);
  const [rate, setRate] = useState<number | null>(current.rate);

  useEffect(() => {
    if (open) {
      setClearType(current.clearType);
      setRank(current.rank);
      setMinBp(current.minBp);
      setRate(current.rate);
    }
    // Only reset on open/fumen-identity change, not on every `current` object identity change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, fumen.sha256, fumen.md5]);

  const calcParamsQuery = useRatingCalcParams(open ? tableSlug : null);
  const myRankQuery = useMyRank(tableSlug, undefined, open);
  const contributionQuery = useRankingContributionRows({
    tableSlug,
    metric: "rating",
    scope: "all",
    sortBy: "value",
    sortDir: "desc",
    userId: undefined,
    enabled: open,
  });

  const isInitialLoading =
    calcParamsQuery.isLoading || myRankQuery.isLoading || contributionQuery.isLoading;
  const config = calcParamsQuery.data?.config ?? null;

  const calcResult = useMemo<CalcResult | null>(() => {
    if (!config) return null;

    const virtualLamp = lampName(clearType);
    const currentLamp = lampName(current.clearType);
    const virtualLevel = resolveLevel(fumen.sha256, fumen.md5, virtualLamp, fumen.level, config);
    const currentResolvedLevel = resolveLevel(fumen.sha256, fumen.md5, currentLamp, fumen.level, config);
    const virtualSongRating = songRating(
      { level: virtualLevel, lamp: virtualLamp, rank: rank ?? "F", bp: minBp, rate },
      config,
    );
    const currentSongRating = songRating(
      {
        level: currentResolvedLevel,
        lamp: currentLamp,
        rank: current.rank ?? "F",
        bp: current.minBp,
        rate: current.rate,
      },
      config,
    );

    let totalImpact: TotalImpactResult;
    const calcParamsData = calcParamsQuery.data;
    if (
      !calcParamsData ||
      myRankQuery.isError ||
      contributionQuery.isError ||
      !myRankQuery.data ||
      !contributionQuery.data
    ) {
      totalImpact = { status: "unavailable", reason: "error" };
    } else if (myRankQuery.data.status !== "ok") {
      totalImpact = {
        status: "unavailable",
        reason: myRankQuery.data.status === "pending" ? "pending" : "no_scores",
      };
    } else {
      const myRank = myRankQuery.data;
      const { topN, maxLevel, expLevelStep } = calcParamsData;
      const entries = contributionQuery.data.entries;

      const matchIndex = entries.findIndex(
        (entry) =>
          (fumen.sha256 != null && entry.sha256 === fumen.sha256) ||
          (fumen.md5 != null && entry.md5 === fumen.md5),
      );
      // No matching row means this fumen is not part of this table's target list (edge case — e.g. the dialog was
      // opened for a chart outside `tableSlug`). Treat its original contribution as 0 and append a synthetic
      // candidate row for the virtual list below.
      const originalRowValue = matchIndex >= 0 ? entries[matchIndex].value : 0;

      const virtualValues = entries.map((entry) => entry.value);
      if (matchIndex >= 0) {
        virtualValues[matchIndex] = virtualSongRating;
      } else {
        virtualValues.push(virtualSongRating);
      }
      virtualValues.sort((left, right) => right - left);

      let nextRawTopN = 0;
      for (let i = 0; i < Math.min(topN, virtualValues.length); i += 1) {
        if (virtualValues[i] > 0) nextRawTopN += virtualValues[i];
      }

      const expDelta = virtualSongRating - originalRowValue;
      const nextTotalExp = myRank.exp + expDelta;
      const nextPlayerLevel = expLevel(nextTotalExp, expLevelStep, maxLevel);
      const nextBmsForce = standardizeRating(nextRawTopN, nextPlayerLevel);

      totalImpact = { status: "ok", currentBmsForce: myRank.bms_force, nextBmsForce };
    }

    return { virtualSongRating, currentSongRating, totalImpact };
  }, [
    config,
    clearType,
    rank,
    minBp,
    rate,
    current.clearType,
    current.rank,
    current.minBp,
    current.rate,
    fumen.sha256,
    fumen.md5,
    fumen.level,
    calcParamsQuery.data,
    myRankQuery.data,
    myRankQuery.isError,
    contributionQuery.data,
    contributionQuery.isError,
  ]);

  const effectiveClearType = clearType ?? 0;
  const effectiveCurrentClearType = current.clearType ?? 0;
  const effectiveRank = rank ?? "F";
  const effectiveCurrentRank = current.rank ?? "F";
  const isFcOrAbove = FC_OR_ABOVE_CLEAR_TYPES.has(effectiveClearType);
  const clearLabels = getClientLabels(clientType ?? "");

  const songUrl = fumen.sha256 || fumen.md5 ? songHref({ sha256: fumen.sha256, md5: fumen.md5 }) : null;

  function handleSetGoal() {
    if (!onSetGoal || !calcResult) return;
    onSetGoal({
      tableSlug,
      fumen,
      clientType: clientType ?? "",
      clearType,
      rank,
      minBp,
      rate,
      projectedRating: calcResult.virtualSongRating,
    });
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden bg-card p-0">
        <DialogHeader className="border-b border-border px-6 py-4">
          <DialogTitle className="text-lg font-semibold">
            {t("ranking.detail.calculator.title")}
          </DialogTitle>
          <div className="mt-1 flex items-start gap-2">
            <span className="mt-0.5 shrink-0 rounded-md border border-primary/40 bg-primary/10 px-2 py-0.5 text-caption font-semibold text-primary">
              {formatTableLevelWithSymbolForDisplay({ tableSymbol: fumen.symbol, level: fumen.level })}
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

        <div className="flex-1 space-y-5 overflow-y-auto px-6 py-4">
          {/* Clear (lamp) control */}
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-caption font-medium text-muted-foreground">
                {t("common.fields.clear")}
              </span>
              <span className="text-caption text-muted-foreground">
                {t("ranking.detail.calculator.current")}: {clearLabels[effectiveCurrentClearType] ?? "-"}
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {Object.keys(CLEAR_TYPE_TO_LAMP_NAME)
                .map((key) => Number(key))
                .map((ct) => {
                  const isSelected = effectiveClearType === ct;
                  const isBaseline = effectiveCurrentClearType === ct;
                  return (
                    <button
                      key={ct}
                      type="button"
                      onClick={() => setClearType(ct)}
                      className={cn(
                        "rounded-full border px-2.5 py-1 text-caption font-medium transition-all",
                        isSelected
                          ? "ring-2 ring-foreground/70 ring-offset-1 ring-offset-background"
                          : "opacity-60 hover:opacity-100",
                        isBaseline && !isSelected && "border-dashed",
                      )}
                      style={CLEAR_BADGE_STYLE[ct] ?? CLEAR_BADGE_STYLE[0]}
                    >
                      {clearLabels[ct] ?? String(ct)}
                    </button>
                  );
                })}
            </div>
          </div>

          {/* Rank control */}
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-caption font-medium text-muted-foreground">
                {t("common.fields.rank")}
              </span>
              <span className="text-caption text-muted-foreground">
                {t("ranking.detail.calculator.current")}: {current.rank ?? "-"}
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {RANK_ORDER.map((r) => {
                const isSelected = effectiveRank === r;
                const isBaseline = effectiveCurrentRank === r;
                return (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setRank(r)}
                    className={cn(
                      "rounded-md border px-2.5 py-1 text-caption font-semibold transition-colors",
                      isSelected
                        ? "border-primary bg-primary/15 text-primary"
                        : "border-border text-muted-foreground hover:text-foreground",
                      isBaseline && !isSelected && "border-dashed border-muted-foreground/60",
                    )}
                  >
                    {r}
                  </button>
                );
              })}
            </div>
          </div>

          {/* BP control */}
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="flex items-center gap-1 text-caption font-medium text-muted-foreground">
                {t("common.fields.bp")}
                {isFcOrAbove && (
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Info className="h-3.5 w-3.5 cursor-help" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-56 text-label">
                        {t("ranking.detail.calculator.bpIgnoredAtFc")}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                )}
              </span>
              <span className="text-caption text-muted-foreground">
                {t("ranking.detail.calculator.current")}: {current.minBp ?? "-"}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="h-9 w-9 shrink-0"
                disabled={isFcOrAbove || (minBp ?? 0) <= 0}
                onClick={() => setMinBp(Math.max(0, (minBp ?? 0) - 1))}
                aria-label={t("ranking.detail.calculator.bpDecreaseAria")}
              >
                <Minus className="h-4 w-4" />
              </Button>
              <Input
                type="number"
                min={0}
                value={minBp ?? 0}
                disabled={isFcOrAbove}
                onChange={(e) => {
                  const next = Number(e.target.value);
                  setMinBp(Number.isFinite(next) ? Math.max(0, Math.trunc(next)) : 0);
                }}
                className="h-9 w-24 text-center tabular-nums"
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="h-9 w-9 shrink-0"
                disabled={isFcOrAbove}
                onClick={() => setMinBp((minBp ?? 0) + 1)}
                aria-label={t("ranking.detail.calculator.bpIncreaseAria")}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* Rate control */}
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-caption font-medium text-muted-foreground">
                {t("common.fields.rate")}
              </span>
              <span className="text-caption text-muted-foreground">
                {t("ranking.detail.calculator.current")}: {current.rate != null ? formatRatePercent(current.rate) : "-"}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={0}
                max={100}
                step={0.01}
                value={rate ?? 0}
                onChange={(e) => setRate(Number(e.target.value))}
                className="h-2 flex-1 cursor-pointer accent-primary"
              />
              <div className="relative w-24 shrink-0">
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
                  className="h-9 pr-6 text-center tabular-nums"
                />
                <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-caption text-muted-foreground">
                  %
                </span>
              </div>
            </div>
          </div>

          {/* Result panel */}
          <div className="space-y-4 rounded-xl border border-border bg-card/60 p-4">
            <div>
              <div className="mb-1 text-caption font-medium text-muted-foreground">
                {t("ranking.detail.calculator.songRatingLabel")}
              </div>
              {isInitialLoading ? (
                <Skeleton className="h-6 w-40" />
              ) : calcResult ? (
                <ValueDelta
                  previous={formatSongRatingValue(calcResult.currentSongRating)}
                  current={formatSongRatingValue(calcResult.virtualSongRating)}
                  diff={formatSongRatingDelta(calcResult.virtualSongRating - calcResult.currentSongRating)}
                />
              ) : (
                <p className="text-label text-muted-foreground">
                  {t("ranking.detail.calculator.totalUnavailableError")}
                </p>
              )}
            </div>

            <div className="border-t border-border/60 pt-4">
              <div className="mb-1 text-caption font-medium text-muted-foreground">
                {t("ranking.detail.calculator.totalBmsforceLabel")}
              </div>
              {isInitialLoading ? (
                <Skeleton className="h-6 w-40" />
              ) : calcResult?.totalImpact.status === "ok" ? (
                <ValueDelta
                  previous={formatBmsforceValue(calcResult.totalImpact.currentBmsForce)}
                  current={formatBmsforceValue(calcResult.totalImpact.nextBmsForce)}
                  diff={formatBmsforceDelta(
                    calcResult.totalImpact.nextBmsForce - calcResult.totalImpact.currentBmsForce,
                  )}
                />
              ) : (
                <div className="text-label text-muted-foreground">
                  <p className="font-medium text-foreground">
                    {t("ranking.detail.calculator.totalUnavailableTitle")}
                  </p>
                  <p>
                    {calcResult?.totalImpact.status === "unavailable" && calcResult.totalImpact.reason === "pending"
                      ? t("ranking.detail.pending")
                      : calcResult?.totalImpact.status === "unavailable" &&
                          calcResult.totalImpact.reason === "no_scores"
                        ? t("ranking.detail.noTableRecords")
                        : t("ranking.detail.calculator.totalUnavailableError")}
                  </p>
                </div>
              )}
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
