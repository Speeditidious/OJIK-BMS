"use client";

import { useState, memo } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, ChevronUp, ChevronRight } from "lucide-react";
import { RecentUpdate, HeatmapDay, ClientTypeFilter } from "@/hooks/use-analysis";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  CLEAR_TYPE_LABELS,
  LR2_CLEAR_TYPE_LABELS,
  BEATORAJA_CLEAR_TYPE_LABELS,
} from "@/components/charts/ClearDistributionChart";
import { displayClearType } from "@/lib/clear-type-display";
import { formatRatePercent } from "@/lib/rate-format";
import { formatTableLevelWithSymbolForDisplay } from "@/lib/table-level-display";
import { songHref } from "@/lib/song-href";
import { formatRelativeDate } from "@/lib/time";
import { localeFromLanguage } from "@/lib/i18n/locale";

// CSS variable refs per internal clear_type (0=NO PLAY, 1=FAILED, 2=ASSIST, 3=EASY, 4=NORMAL, 5=HARD, 6=EXHARD, 7=FC, 8=PERFECT, 9=MAX)
const CLEAR_BADGE_STYLE: Record<number, React.CSSProperties> = {
  0: { borderColor: "hsl(var(--clear-no-play))", background: "hsl(var(--clear-no-play)/0.4)", color: "hsl(var(--muted-foreground))" },
  1: { borderColor: "hsl(var(--clear-failed)/0.6)", background: "hsl(var(--clear-failed)/0.15)", color: "hsl(var(--clear-failed))" },
  2: { borderColor: "hsl(var(--clear-assist)/0.6)", background: "hsl(var(--clear-assist)/0.2)", color: "hsl(220 20% 9%)" },
  3: { borderColor: "hsl(var(--clear-easy)/0.6)", background: "hsl(var(--clear-easy)/0.2)", color: "hsl(220 20% 9%)" },
  4: { borderColor: "hsl(var(--clear-normal)/0.6)", background: "hsl(var(--clear-normal)/0.2)", color: "hsl(220 20% 9%)" },
  5: { borderColor: "hsl(var(--clear-hard)/0.6)", background: "hsl(var(--clear-hard)/0.2)", color: "hsl(220 20% 9%)" },
  6: { borderColor: "hsl(var(--clear-exhard)/0.6)", background: "hsl(var(--clear-exhard)/0.2)", color: "hsl(220 20% 9%)" },
  7: { borderColor: "hsl(var(--clear-fc)/0.6)", background: "hsl(var(--clear-fc)/0.2)", color: "hsl(220 20% 9%)" },
  8: { borderColor: "hsl(var(--clear-perfect)/0.6)", background: "hsl(var(--clear-perfect)/0.2)", color: "hsl(220 20% 9%)" },
  9: { borderColor: "hsl(var(--clear-max)/0.6)", background: "hsl(var(--clear-max)/0.2)", color: "hsl(220 20% 9%)" },
};

function getClientLabels(clientType: string) {
  if (clientType === "lr2") return LR2_CLEAR_TYPE_LABELS;
  if (clientType === "beatoraja") return BEATORAJA_CLEAR_TYPE_LABELS;
  return CLEAR_TYPE_LABELS;
}

export function clearBadge(
  clearType: number | null,
  clientType: string,
  score?: { exscore?: number | null; rate?: number | null },
) {
  if (clearType === null) return null;
  const displayType = displayClearType(clearType, score) ?? clearType;
  const labels = getClientLabels(clientType);
  const label = labels[displayType] ?? String(displayType);
  const style = CLEAR_BADGE_STYLE[displayType] ?? CLEAR_BADGE_STYLE[0];
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-caption font-medium border shrink-0"
      style={style}
    >
      {label}
    </span>
  );
}

/** Plain text version of clearBadge — no badge decoration, no color override. */
export function clearText(
  clearType: number | null,
  clientType: string,
  score?: { exscore?: number | null; rate?: number | null },
) {
  if (clearType === null) return null;
  const displayType = displayClearType(clearType, score) ?? clearType;
  const labels = getClientLabels(clientType);
  const label = labels[displayType] ?? String(displayType);
  return (
    <span className="text-label">
      {label}
    </span>
  );
}

const CLEAR_TEXT_COLOR: Record<number, string> = {
  0: "hsl(var(--muted-foreground))",
  1: "hsl(var(--clear-failed))",
  2: "hsl(var(--clear-assist))",
  3: "hsl(var(--clear-easy))",
  4: "hsl(var(--clear-normal))",
  5: "hsl(var(--clear-hard))",
  6: "hsl(var(--clear-exhard))",
  7: "hsl(var(--clear-fc))",
  8: "hsl(var(--clear-perfect))",
  9: "hsl(var(--clear-max))",
};

/** Like clearText, but the label is tinted by clear-type color (for color-less rows). */
export function clearTextColored(
  clearType: number | null,
  clientType: string,
  score?: { exscore?: number | null; rate?: number | null },
) {
  if (clearType === null) return null;
  const displayType = displayClearType(clearType, score) ?? clearType;
  const labels = getClientLabels(clientType);
  const label = labels[displayType] ?? String(displayType);
  return (
    <span className="text-label font-semibold" style={{ color: CLEAR_TEXT_COLOR[displayType] ?? CLEAR_TEXT_COLOR[0] }}>
      {label}
    </span>
  );
}

export const UpdateRow = memo(function UpdateRow({ u }: { u: RecentUpdate }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const songName =
    u.title ??
    (u.fumen_sha256 ? u.fumen_sha256.slice(0, 8) + "…" : null) ??
    (u.fumen_md5 ? u.fumen_md5.slice(0, 8) + "…" : t("common.states.noData"));
  const rankChanged = u.rank !== null;
  const firstClear = (u.clear_type ?? 0) >= 3;

  return (
    <div
      className={`py-2 border-b border-border/40 last:border-0 cursor-pointer${firstClear ? " border-l-2 border-l-warning pl-2" : ""}`}
      onClick={() => setExpanded((prev) => !prev)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1 min-w-0">
          <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
            {firstClear && (
              <span
                className="inline-flex items-center rounded-full px-2 py-0.5 text-caption font-medium border shrink-0"
                style={{ borderColor: "hsl(var(--warning)/0.6)", background: "hsl(var(--warning)/0.15)", color: "hsl(var(--warning))" }}
              >
                ★ First Clear
              </span>
            )}
            {clearBadge(u.clear_type, u.client_type, { exscore: u.exscore, rate: u.rate })}
            {(u.fumen_sha256 || u.fumen_md5) ? (
              <a
                href={songHref({ fumen_id: u.fumen_id, sha256: u.fumen_sha256, md5: u.fumen_md5 })}
                className="text-label font-medium truncate max-w-[200px] hover:text-primary transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                {songName}
              </a>
            ) : (
              <span className="text-label font-medium truncate max-w-[200px]">{songName}</span>
            )}
          </div>

          {u.difficulty_levels.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              {u.difficulty_levels.map(({ symbol, level }, i) => (
                <span
                  key={i}
                  className="inline-flex items-center rounded px-1.5 py-0 text-caption font-medium border border-primary/40 text-primary bg-primary/10"
                >
                  {formatTableLevelWithSymbolForDisplay({ tableSymbol: symbol, level })}
                </span>
              ))}
            </div>
          )}

          <div className="flex gap-2 flex-wrap">
            {rankChanged && (
              <span className="text-caption text-muted-foreground">
                Rank: {u.rank}
              </span>
            )}
            {u.exscore !== null && (
              <span className="text-caption text-muted-foreground font-mono">
                EX: {u.exscore}
              </span>
            )}
          </div>
        </div>

        <div className="flex flex-col items-end gap-1 shrink-0">
          <div className="flex items-center gap-1">
            <span className="text-caption text-muted-foreground uppercase">{u.client_type}</span>
            {expanded ? (
              <ChevronUp className="h-3 w-3 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-3 w-3 text-muted-foreground" />
            )}
          </div>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-border/30 pt-2 mt-2 grid grid-cols-2 gap-x-4 gap-y-1">
          {u.min_bp !== null && (
            <span className="text-caption text-muted-foreground">
              BP: {u.min_bp}
            </span>
          )}
          {u.play_count !== null && (
            u.is_initial_sync ? (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="text-caption text-muted-foreground cursor-help">
                      {t("dashboard.scoreUpdates.plays")}: - → {u.play_count}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent className="text-label">
                    {t("dashboard.activity.firstSync")} — {t("common.states.noData")}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            ) : u.prev_play_count !== null ? (
              <span className="text-caption text-muted-foreground">
                {t("dashboard.scoreUpdates.plays")}: {u.prev_play_count} → {u.play_count}
              </span>
            ) : (
              <span className="text-caption text-muted-foreground">
                {t("dashboard.scoreUpdates.plays")}: {u.play_count}
              </span>
            )
          )}
          {u.rate !== null && (
            <span className="text-caption text-muted-foreground">
              {t("dashboard.scoreUpdates.rate")}: {formatRatePercent(u.rate)}
            </span>
          )}
          {u.artist && (
            <span className="text-caption text-muted-foreground truncate">
              {u.artist}
            </span>
          )}
        </div>
      )}
    </div>
  );
});

// ── Thread row helpers ─────────────────────────────────────────────────────────

function formatDateLabel(dateStr: string, locale: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString(locale, { month: "short", day: "numeric" });
}


// ── Thread row list component ──────────────────────────────────────────────────

const PAGE_SIZE = 30;

interface Props {
  clientType?: ClientTypeFilter;
  heatmapData?: HeatmapDay[];
  ratingUpdatesByDate?: Record<string, number>;
  firstSyncDates?: { lr2?: string; beatoraja?: string };
  onDayClick?: (dateStr: string) => void;
  emptyMessage?: string;
  userId?: string;
}

export function RecentActivity({
  heatmapData = [],
  ratingUpdatesByDate = {},
  firstSyncDates,
  onDayClick,
  emptyMessage,
  userId,
}: Props) {
  const { t, i18n } = useTranslation();
  const dateLocale = localeFromLanguage(i18n.language);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const allDays = heatmapData
    .filter((d) => {
      const isFirstSync = firstSyncDates?.lr2 === d.date || firstSyncDates?.beatoraja === d.date;
      const ratingCount = isFirstSync ? 0 : (ratingUpdatesByDate[d.date] ?? 0);
      return d.updates > 0 || (d.new_plays ?? 0) > 0 || d.plays > 0 || ratingCount > 0;
    })
    .slice()
    .sort((a, b) => (a.date < b.date ? 1 : -1));

  const visibleDays = allDays.slice(0, visibleCount);
  const remaining = allDays.length - visibleCount;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("dashboard.activity.title")}</CardTitle>
        <CardDescription>{t("common.states.noRecords")}</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        {allDays.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-muted-foreground text-body px-6">
            {emptyMessage ?? t("dashboard.activity.noRecords")}
          </div>
        ) : (
          <div>
            {visibleDays.map((day) => (
              <div
                key={day.date}
                role="button"
                tabIndex={0}
                className="flex items-center justify-between px-6 py-3 border-b border-border/40 cursor-pointer hover:bg-muted/50 transition-colors"
                onClick={() => onDayClick?.(day.date)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onDayClick?.(day.date);
                  }
                }}
              >
                <div className="flex flex-col gap-0.5">
                  <span className="text-label font-semibold">{formatDateLabel(day.date, dateLocale)}</span>
                  <span className="text-caption text-muted-foreground">{formatRelativeDate(day.date + "T00:00:00", "--", t)}</span>
                </div>
                <div className="flex items-center gap-2">
                  {/* Order: score updates → new plays → rating updates → play count */}
                  <span
                    className="text-caption bg-muted rounded px-1.5 py-0.5"
                    style={{ color: "hsl(var(--warning))" }}
                  >
                    {t("dashboard.activity.scoreUpdates", { count: day.updates })}
                  </span>
                  {(day.new_plays ?? 0) > 0 && (
                    <span
                      className="text-caption bg-muted rounded px-1.5 py-0.5"
                      style={{ color: "hsl(var(--primary))" }}
                    >
                      {t("dashboard.activity.newPlays", { count: day.new_plays })}
                    </span>
                  )}
                  {(ratingUpdatesByDate[day.date] ?? 0) > 0 && !(firstSyncDates?.lr2 === day.date || firstSyncDates?.beatoraja === day.date) && (
                    <span
                      className="text-caption bg-muted rounded px-1.5 py-0.5"
                      style={{ color: "hsl(var(--chart-rating))" }}
                    >
                      {t("dashboard.activity.ratingUpdates", { count: ratingUpdatesByDate[day.date] })}
                    </span>
                  )}
                  <span
                    className="text-caption bg-muted rounded px-1.5 py-0.5"
                    style={{ color: "hsl(var(--chart-play))" }}
                  >
                    {t("dashboard.activity.plays", { count: day.plays })}
                  </span>
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                </div>
              </div>
            ))}

            {remaining > 0 && (
              <div
                className="flex items-center justify-center gap-2 px-6 py-3 cursor-pointer hover:bg-muted/50 transition-colors text-label text-muted-foreground"
                onClick={() => setVisibleCount((prev) => prev + PAGE_SIZE)}
              >
                <span>Show more ({remaining})</span>
                <ChevronDown className="h-4 w-4" />
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
