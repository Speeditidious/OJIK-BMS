"use client";

import type { ReactNode } from "react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { RankingContributionEntry } from "@/lib/ranking-types";
import { formatRatingContributionCardRankLabel } from "@/lib/rating-detail-display-core.mjs";
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
}

function ContributionCard({ entry }: ContributionCardProps) {
  const { t } = useTranslation();

  const title = fumenTitleText(entry.title, t("common.states.noData"));
  const artist = fumenArtistText(entry.artist);
  const rankLabel = formatRatingContributionCardRankLabel(entry.rank_grade, entry.max_minus_score ?? null);

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
          <div className="rating-value-cell shrink-0 rounded-[10px] px-3 py-1.5">
            <span className="text-[21px] font-extrabold tabular-nums leading-none">
              {ratingInt}
            </span>
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
}

export function RatingContributionGrid({ entries, leadingSlot }: RatingContributionGridProps) {
  const { t } = useTranslation();

  const filtered = useMemo(
    () =>
      entries.filter((e) => {
        if (e.was_in_top_n === true && e.is_in_top_n === false) return false;
        return (
          Math.abs(e.delta_rating ?? 0) > 1e-9 ||
          (e.was_in_top_n === false && e.is_in_top_n === true)
        );
      }),
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
          <ContributionCard key={entry.detail_score_id ?? i} entry={entry} />
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
            <ContributionCard key={entry.detail_score_id ?? i} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}
