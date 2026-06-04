"use client";

import { useState } from "react";
import Link from "next/link";
import { Flame } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePopularFumens } from "@/hooks/use-popular-fumens";
import { cn } from "@/lib/utils";
import { songHref } from "@/lib/song-href";
import { fumenArtistText, fumenTitleText } from "@/lib/fumen-display";
import type { PopularRange } from "@/types";

const RANGES: PopularRange[] = ["weekly", "monthly", "all_time"];
const GRID = "grid-cols-[2.5rem_minmax(0,1fr)_5rem_3.5rem]";

function rankClass(rank: number) {
  if (rank === 1) return "text-yellow-400";
  if (rank === 2) return "text-zinc-300";
  if (rank === 3) return "text-amber-600";
  return "text-muted-foreground";
}

export function PopularFumensDialog() {
  const { t } = useTranslation();
  const [range, setRange] = useState<PopularRange>("weekly");
  const { data, isLoading } = usePopularFumens(range, 10);
  const rows = data?.items ?? [];
  const asOf = data?.as_of ?? null;

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <Flame className="h-4 w-4 text-primary" />
          {t("songs.popular.button")}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Flame className="h-5 w-5 text-primary" />
            {t("songs.popular.title", { range: t(`songs.popular.range.${range}`) })}
          </DialogTitle>
          <p className="text-caption text-muted-foreground">
            {asOf ? t("songs.popular.asOf", { time: new Date(asOf).toLocaleString() }) : "\u00a0"}
          </p>
        </DialogHeader>

        <Tabs value={range} onValueChange={(value) => setRange(value as PopularRange)}>
          <TabsList className="grid w-full grid-cols-3">
            {RANGES.map((r) => (
              <TabsTrigger key={r} value={r}>
                {t(`songs.popular.range.${r}`)}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

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
              <Link
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
                <span className="text-right tabular-nums text-label">{row.played_user_count.toLocaleString()}</span>
                <span className="text-right tabular-nums text-label">{row.play_count.toLocaleString()}</span>
              </Link>
            ))
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
