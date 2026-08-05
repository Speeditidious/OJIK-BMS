"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePopularFumens } from "@/hooks/use-popular-fumens";
import { cn } from "@/lib/utils";
import { songHref } from "@/lib/song-href";
import { fumenArtistText, fumenTitleText } from "@/lib/fumen-display";
import { rankClass } from "@/lib/rank-color";
import { timeAgo } from "@/lib/time";
import type { PopularRange, PopularSortBy } from "@/types";

const RANGES: PopularRange[] = ["weekly", "monthly", "all_time"];
const SORT_OPTIONS: PopularSortBy[] = ["players", "plays"];
const GRID = "grid-cols-[2.5rem_minmax(0,1fr)_5rem_3.5rem]";

interface PopularFumensTableProps {
  /**
   * Controlled range value. When omitted, the component manages its own
   * `range` state internally (defaulting to "weekly") so it works as a
   * fully self-contained widget with zero required props.
   */
  range?: PopularRange;
  /**
   * Notified whenever the range tab changes. Required together with
   * `range` for controlled usage — e.g. `PopularFumensDialog` lifts this
   * state into itself (a component that stays mounted across the dialog's
   * open/close cycle) so the selection survives close→reopen, since
   * `PopularFumensTable` itself gets unmounted whenever `DialogContent`
   * closes.
   */
  onRangeChange?: (range: PopularRange) => void;
  /** Controlled sortBy value, mirrors `range` above. */
  sortBy?: PopularSortBy;
  /** Notified whenever the sortBy tab changes. */
  onSortByChange?: (sortBy: PopularSortBy) => void;
}

/**
 * Self-contained "TOP 10 popular fumens" widget. Supports the standard
 * controlled/uncontrolled pattern for `range`/`sortBy`: pass both value +
 * change-handler props to let a parent own the state (e.g. so it survives
 * the widget being unmounted, as happens inside a closing Dialog); omit
 * them entirely to let the component manage its own state, so it can also
 * be dropped inline on a page with no parent-managed state at all.
 */
export function PopularFumensTable({
  range: controlledRange,
  onRangeChange,
  sortBy: controlledSortBy,
  onSortByChange,
}: PopularFumensTableProps = {}) {
  const { t } = useTranslation();
  const [uncontrolledRange, setUncontrolledRange] = useState<PopularRange>("weekly");
  const [uncontrolledSortBy, setUncontrolledSortBy] = useState<PopularSortBy>("players");
  const range = controlledRange ?? uncontrolledRange;
  const sortBy = controlledSortBy ?? uncontrolledSortBy;
  const setRange = onRangeChange ?? setUncontrolledRange;
  const setSortBy = onSortByChange ?? setUncontrolledSortBy;
  const { data, isLoading } = usePopularFumens(range, 10, sortBy);
  const rows = data?.items ?? [];
  const asOf = data?.as_of ?? null;

  return (
    <div className="flex h-full flex-col">
      <p className="mb-3 min-h-4 text-right text-caption text-muted-foreground">
        {asOf ? t("songs.popular.asOf", { time: timeAgo(asOf, t) }) : " "}
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

      <div className="mt-3 flex justify-center">
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

      <div className="mt-3 flex-1 rounded-lg border border-border overflow-hidden">
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
            <div
              key={row.fumen_id}
              className={cn("grid gap-2 px-3 py-2 items-center border-b border-border/50 last:border-0", GRID)}
            >
              <span className={cn("text-center tabular-nums font-bold", rankClass(row.rank))}>
                {row.rank}
              </span>
              <span className="min-w-0">
                <a
                  href={songHref({ sha256: row.sha256, md5: row.md5 })}
                  className="block truncate text-label text-foreground transition-colors hover:text-primary"
                >
                  {fumenTitleText(row.title)}
                </a>
                <span className="block truncate text-caption text-muted-foreground">{fumenArtistText(row.artist)}</span>
              </span>
              <span className={cn("text-right tabular-nums text-label", sortBy === "players" && "font-semibold text-foreground")}>
                {row.played_user_count.toLocaleString()}
              </span>
              <span className={cn("text-right tabular-nums text-label", sortBy === "plays" && "font-semibold text-foreground")}>
                {row.play_count.toLocaleString()}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
