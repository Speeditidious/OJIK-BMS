"use client";

import { useState, memo } from "react";
import Link from "next/link";
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

export const UpdateRow = memo(function UpdateRow({ u }: { u: RecentUpdate }) {
  const [expanded, setExpanded] = useState(false);
  const songName =
    u.title ??
    (u.fumen_sha256 ? u.fumen_sha256.slice(0, 8) + "…" : null) ??
    (u.fumen_md5 ? u.fumen_md5.slice(0, 8) + "…" : "(알 수 없음)");
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
                ★ 첫 클리어
              </span>
            )}
            {clearBadge(u.clear_type, u.client_type, { exscore: u.exscore, rate: u.rate })}
            {(u.fumen_sha256 || u.fumen_md5) ? (
              <Link
                href={`/songs/${u.fumen_sha256 ?? u.fumen_md5}`}
                className="text-label font-medium truncate max-w-[200px] hover:text-primary transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                {songName}
              </Link>
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
                  {symbol}{level}
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
                      플레이 수: - → {u.play_count}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent className="text-label">
                    첫 동기화 — 이전 플레이 횟수 불명
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            ) : u.prev_play_count !== null ? (
              <span className="text-caption text-muted-foreground">
                플레이 수: {u.prev_play_count} → {u.play_count}
              </span>
            ) : (
              <span className="text-caption text-muted-foreground">
                플레이 수: {u.play_count}
              </span>
            )
          )}
          {u.rate !== null && (
            <span className="text-caption text-muted-foreground">
              스코어율: {formatRatePercent(u.rate)}
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

function formatDateLabel(dateStr: string): string {
  const [, m, d] = dateStr.split("-").map(Number);
  return `${m}월 ${d}일`;
}

function formatRelativeTime(dateStr: string): string {
  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const yesterdayStr = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, "0")}-${String(yesterday.getDate()).padStart(2, "0")}`;

  if (dateStr === todayStr) return "오늘";
  if (dateStr === yesterdayStr) return "어제";

  const diffMs = today.getTime() - new Date(dateStr + "T00:00:00").getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 7) return `${diffDays}일 전`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}주 전`;
  return `${Math.floor(diffDays / 30)}개월 전`;
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
  emptyMessage = "활동 내역이 없습니다.",
  userId,
}: Props) {
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
        <CardTitle>최근 활동</CardTitle>
        <CardDescription>날짜를 클릭하면 해당 날의 기록을 확인합니다.</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        {allDays.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-muted-foreground text-body px-6">
            {emptyMessage}
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
                  <span className="text-label font-semibold">{formatDateLabel(day.date)}</span>
                  <span className="text-caption text-muted-foreground">{formatRelativeTime(day.date)}</span>
                </div>
                <div className="flex items-center gap-2">
                  {/* Order: 갱신 기록 → 신규 기록 → 레이팅 갱신 → 플레이 횟수 */}
                  <span
                    className="text-caption bg-muted rounded px-1.5 py-0.5"
                    style={{ color: "hsl(var(--warning))" }}
                  >
                    갱신 {day.updates}건
                  </span>
                  {(day.new_plays ?? 0) > 0 && (
                    <span
                      className="text-caption bg-muted rounded px-1.5 py-0.5"
                      style={{ color: "hsl(var(--primary))" }}
                    >
                      신규 {day.new_plays}건
                    </span>
                  )}
                  {(ratingUpdatesByDate[day.date] ?? 0) > 0 && !(firstSyncDates?.lr2 === day.date || firstSyncDates?.beatoraja === day.date) && (
                    <span
                      className="text-caption bg-muted rounded px-1.5 py-0.5"
                      style={{ color: "hsl(var(--chart-rating))" }}
                    >
                      레이팅 갱신 {ratingUpdatesByDate[day.date]}건
                    </span>
                  )}
                  <span
                    className="text-caption bg-muted rounded px-1.5 py-0.5"
                    style={{ color: "hsl(var(--chart-play))" }}
                  >
                    플레이 {day.plays}회
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
                <span>더보기 ({remaining}개 남음)</span>
                <ChevronDown className="h-4 w-4" />
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
