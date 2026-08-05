"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePopularFumens } from "@/hooks/use-popular-fumens";
import { cn } from "@/lib/utils";
import { songHref } from "@/lib/song-href";
import { fumenArtistText, fumenTitleText } from "@/lib/fumen-display";
import { rankClass } from "@/lib/rank-color";
import type { PopularRange, PopularSortBy } from "@/types";

const RANGES: PopularRange[] = ["weekly", "monthly", "all_time"];
const SORT_OPTIONS: PopularSortBy[] = ["players", "plays"];
const GRID = "grid-cols-[2.5rem_minmax(0,1fr)_5rem_3.5rem]";

interface PopularFumensTableProps {
  /**
   * Optional notification callback fired whenever the internally-owned
   * `range` changes (including on mount, with the initial value). Lets a
   * host like `PopularFumensDialog` mirror the current range into its own
   * title without lifting the range state itself — this component remains
   * the single source of truth for range/sortBy/data.
   */
  onRangeChange?: (range: PopularRange) => void;
}

/**
 * Self-contained "TOP 10 popular fumens" widget: owns its own range/sortBy
 * state and data fetching, so it can be reused as-is both inside a dialog
 * and inline on a page.
 */
export function PopularFumensTable({ onRangeChange }: PopularFumensTableProps = {}) {
  const { t } = useTranslation();
  const [range, setRange] = useState<PopularRange>("weekly");
  const [sortBy, setSortBy] = useState<PopularSortBy>("players");
  const { data, isLoading } = usePopularFumens(range, 10, sortBy);
  const rows = data?.items ?? [];
  const asOf = data?.as_of ?? null;

  useEffect(() => {
    onRangeChange?.(range);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range]);

  return (
    <div>
      <p className="text-caption text-muted-foreground">
        {asOf ? t("songs.popular.asOf", { time: new Date(asOf).toLocaleString() }) : " "}
      </p>

      <Tabs value={range} onValueChange={(value) => setRange(value as PopularRange)}>
        <TabsList className="grid w-full grid-cols-3">
          {RANGES.map((r) => (
            <TabsTrigger key={r} value={r}>
              {t(`songs.popular.range.${r}`)}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <div className="flex justify-center">
        <Tabs value={sortBy} onValueChange={(v) => setSortBy(v as PopularSortBy)}>
          <TabsList className="grid grid-cols-2 w-56">
            {SORT_OPTIONS.map((opt) => (
              <TabsTrigger key={opt} value={opt}>
                {t(`songs.popular.sortBy.${opt}`)}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      <div className="rounded-lg border border-border overflow-hidden">
        <div className={cn("grid gap-2 px-3 py-2 bg-secondary/50 border-b border-border text-caption font-semibold text-muted-foreground", GRID)}>
          <span className="text-center">{t("songs.popular.rank")}</span>
          <span>{t("songs.columns.titleArtist")}</span>
          <span className="text-right">{t("songs.columns.players")}</span>
          <span className="text-right">{t("songs.columns.totalPlays")}</span>
        </div>

        {isLoading ? (
          Array.from({ length: 10 }).map((_, index) => (
            <div key={index} className="h-11 border-b border-border/50 last:border-0 bg-secondary/30 animate-pulse" />
          ))
        ) : rows.length === 0 ? (
          <div className="py-10 text-center text-label text-muted-foreground">
            {t("songs.popular.empty")}
          </div>
        ) : (
          rows.map((row) => (
            <a
              key={row.fumen_id}
              href={songHref({ sha256: row.sha256, md5: row.md5 })}
              className={cn("group grid gap-2 px-3 py-2 items-center border-b border-border/50 last:border-0 transition-colors hover:bg-secondary/40", GRID)}
            >
              <span className={cn("text-center tabular-nums font-bold", rankClass(row.rank))}>
                {row.rank}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-label text-foreground transition-colors group-hover:text-primary">{fumenTitleText(row.title)}</span>
                <span className="block truncate text-caption text-muted-foreground">{fumenArtistText(row.artist)}</span>
              </span>
              <span className={cn("text-right tabular-nums text-label", sortBy === "players" && "font-semibold text-foreground")}>
                {row.played_user_count.toLocaleString()}
              </span>
              <span className={cn("text-right tabular-nums text-label", sortBy === "plays" && "font-semibold text-foreground")}>
                {row.play_count.toLocaleString()}
              </span>
            </a>
          ))
        )}
      </div>
    </div>
  );
}
