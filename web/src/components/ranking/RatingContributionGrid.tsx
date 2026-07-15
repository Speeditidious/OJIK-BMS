"use client";

import type { ReactNode } from "react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Calculator } from "lucide-react";
import type { RankingContributionEntry } from "@/lib/ranking-types";
import {
  formatRatingContributionCardRankLabel,
  getDayStatRatingContributionEntries,
} from "@/lib/rating-detail-display-core.mjs";
import { formatRatePercent } from "@/lib/rate-format";
import { fumenTitleText, fumenArtistText } from "@/lib/fumen-display";
import { formatTableLevelWithSymbolForDisplay } from "@/lib/table-level-display";
import { cn } from "@/lib/utils";

// ── Color helpers ─────────────────────────────────────────────────────────────

const CT_CSS_VAR: Record<number, string> = {
  0: "--clear-no-play",
  1: "--clear-failed",
  2: "--clear-assist",
  3: "--clear-easy",
  4: "--clear-normal",
  5: "--clear-hard",
  6: "--clear-exhard",
  7: "--clear-fc",
  8: "--clear-perfect",
  9: "--clear-max",
};

function clearTypeColor(ct: number): string {
  const v = CT_CSS_VAR[ct] ?? "--clear-no-play";
  return `hsl(var(${v}))`;
}

const RANK_COLOR: Record<string, string> = {
  F: "hsl(var(--clear-no-play))",
  E: "hsl(var(--clear-failed))",
  D: "hsl(var(--clear-assist))",
  C: "hsl(var(--clear-easy))",
  B: "hsl(var(--clear-normal))",
  A: "hsl(27 65% 55%)",
  AA: "hsl(220 15% 72%)",
  AAA: "hsl(46 80% 60%)",
  "MAX-": "hsl(330 65% 78%)",
  MAX: "hsl(var(--clear-max))",
};

function rankColor(rank: string | null): string {
  return RANK_COLOR[rank ?? "F"] ?? "hsl(var(--muted-foreground))";
}

// ── Lamp abbreviation ─────────────────────────────────────────────────────────

const LAMP_ABBR: Record<number, string> = {
  0: "NO PLAY",
  1: "FAILED",
  2: "ASSIST",
  3: "EASY",
  4: "NORMAL",
  5: "HARD",
  6: "EXH",
  7: "FC",
  8: "PFC",
  9: "MAX",
};

// ── Song card ─────────────────────────────────────────────────────────────────

interface ContributionCardProps {
  entry: RankingContributionEntry;
  /**
   * When provided, the rating-value block becomes clickable and opens the
   * what-if calculator for this entry. Mirrors the cell-scoped hover
   * treatment used by `ContributionTable`'s rating cell (entry point 1),
   * but implemented as an absolutely-positioned overlay button rather than
   * wrapping the value itself — this component renders inside
   * `DayStatSheet`'s image-export target, and the button/icon chrome must
   * not appear in the exported image while the numeric rating value must.
   * The overlay carries `data-export-exclude` (see `capture-utils.ts`)
   * so it is dropped from the capture; the value `<div>` beneath it is a
   * plain sibling and always survives.
   */
  onOpenCalculator?: (entry: RankingContributionEntry) => void;
}

function ContributionCard({ entry, onOpenCalculator }: ContributionCardProps) {
  const { t } = useTranslation();

  const title = fumenTitleText(entry.title, t("common.states.noData"));
  const artist = fumenArtistText(entry.artist);
  const rankLabel = formatRatingContributionCardRankLabel(
    entry.rank_grade,
    entry.max_minus_score ?? null,
    entry.clear_type,
  );

  const lampColor = clearTypeColor(entry.clear_type);
  const lampAbbr = LAMP_ABBR[entry.clear_type] ?? String(entry.clear_type);
  const rankCol = rankColor(entry.rank_grade);

  // Use the per-entry table symbol (e.g. "sl10"), matching the rating-detail table.
  const levelAbbr = formatTableLevelWithSymbolForDisplay({
    tableSymbol: entry.symbol,
    level: entry.level,
  });
  const ratingInt = Math.round(entry.value).toLocaleString();

  // Rank change
  const currentRankLabel = `#${entry.rank}`;
  const prevRankLabel = entry.previous_rank != null ? `#${entry.previous_rank}` : null;
  const rankChanged = prevRankLabel != null && entry.previous_rank !== entry.rank;

  return (
    <div
      data-day-sheet-split-block
      className="flex rounded-xl border border-border/50 bg-card shadow-sm overflow-hidden hover:shadow-md transition-shadow"
    >
      {/* Left lamp bar */}
      <div className="w-[6px] shrink-0" style={{ backgroundColor: lampColor }} />

      {/* Card body */}
      <div className="flex flex-col flex-1 min-w-0 px-3.5 py-3 gap-1.5">
        {/* Top row: level + lamp badge + rank text | rating block */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex shrink-0 items-center gap-1.5 whitespace-nowrap">
            {/* Level abbreviation */}
            <span className="text-[17px] font-extrabold text-foreground leading-none whitespace-nowrap">
              {levelAbbr}
            </span>

            {/* Lamp text */}
            <span
              className="text-[17px] font-extrabold leading-none whitespace-nowrap"
              style={{ color: lampColor }}
            >
              {lampAbbr}
            </span>

            {/* Rank text */}
            {rankLabel && (
              <span
                className="text-[17px] font-extrabold leading-none whitespace-nowrap"
                style={{ color: rankCol }}
              >
                {rankLabel}
              </span>
            )}
          </div>

          {/* Rating block — uses the same theme-aware tokens as the
              rating-detail table's rating column (handles light + dark). */}
          <div className="relative shrink-0">
            <div className="rating-value-cell rounded-[10px] px-3 py-1.5">
              <span className="text-[21px] font-extrabold tabular-nums leading-none">
                {ratingInt}
              </span>
            </div>
            {onOpenCalculator && (
              <button
                type="button"
                data-export-exclude
                data-rating-cell=""
                className="group absolute inset-0 flex items-center justify-end rounded-[10px] px-3 transition-colors hover:bg-foreground/10 hover:ring-1 hover:ring-inset hover:ring-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/40"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenCalculator(entry);
                }}
                aria-label={t("ranking.detail.calculator.openAria", { title })}
              >
                <Calculator className="h-3.5 w-3.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
              </button>
            )}
          </div>
        </div>

        {/* Title + artist */}
        <div className="min-w-0">
          <p className="text-[16px] font-bold leading-snug truncate text-foreground">{title}</p>
          {artist && (
            <p className="text-[12.5px] leading-snug truncate text-muted-foreground">{artist}</p>
          )}
        </div>

        {/* Divider */}
        <div className="h-px bg-border/40" />

        {/* Bottom row: BP + accuracy + rank change */}
        <div className="flex items-center justify-between gap-2 text-[13px] text-muted-foreground">
          <div className="flex items-center gap-3">
            {entry.min_bp != null && (
              <span className="tabular-nums">BP {entry.min_bp}</span>
            )}
            {entry.rate != null && (
              <span className="tabular-nums">Rate {formatRatePercent(entry.rate)}</span>
            )}
          </div>

          {/* Rank position */}
          <div className="flex items-center gap-1 shrink-0 tabular-nums">
            {rankChanged ? (
              <span>
                {prevRankLabel} → {currentRankLabel}
              </span>
            ) : (
              <span>{currentRankLabel}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Grid ──────────────────────────────────────────────────────────────────────

interface RatingContributionGridProps {
  entries: RankingContributionEntry[];
  /**
   * Optional summary block floated to the left half. The rating-change cards
   * then flow beside it and reclaim the full width once they pass its bottom.
   */
  leadingSlot?: ReactNode;
  /**
   * When provided, each card's rating-value block opens the what-if
   * calculator for that entry. See `ContributionCard`'s `onOpenCalculator`
   * doc for the image-export exclusion note.
   */
  onOpenCalculator?: (entry: RankingContributionEntry) => void;
}

export function RatingContributionGrid({ entries, leadingSlot, onOpenCalculator }: RatingContributionGridProps) {
  const { t } = useTranslation();

  const filtered = useMemo<RankingContributionEntry[]>(
    () => getDayStatRatingContributionEntries(entries),
    [entries],
  );

  // No leading slot → keep the simple full-width grid behaviour.
  if (!leadingSlot) {
    if (filtered.length === 0) {
      return (
        <p className="text-caption text-muted-foreground py-2">
          {t("dashboard.daySheet.noRatingChange")}
        </p>
      );
    }
    return (
      <div className={cn("grid gap-3", "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4")}>
        {filtered.map((entry, i) => (
          <ContributionCard key={entry.detail_score_id ?? i} entry={entry} onOpenCalculator={onOpenCalculator} />
        ))}
      </div>
    );
  }

  // Summary card spans the full width (its internal EXP | deltas split uses the
  // whole row), and all contribution cards flow in a grid below it.
  return (
    <div className="space-y-3">
      <div data-day-sheet-split-block>{leadingSlot}</div>
      {filtered.length === 0 ? (
        <p data-day-sheet-split-block className="text-caption text-muted-foreground py-2">
          {t("dashboard.daySheet.noRatingChange")}
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((entry, i) => (
            <ContributionCard key={entry.detail_score_id ?? i} entry={entry} onOpenCalculator={onOpenCalculator} />
          ))}
        </div>
      )}
    </div>
  );
}
