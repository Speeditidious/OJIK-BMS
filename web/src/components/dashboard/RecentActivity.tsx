"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useRecentUpdates, RecentUpdate, ClientTypeFilter } from "@/hooks/use-analysis";
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

// CSS variable refs per internal clear_type (0=NO PLAY, 1=FAILED, 2=ASSIST, 3=EASY, 4=NORMAL, 5=HARD, 6=EXHARD, 7=FC, 8=PERFECT, 9=MAX)
const CLEAR_BADGE_STYLE: Record<number, React.CSSProperties> = {
  0: { borderColor: "hsl(var(--clear-no-play))", background: "hsl(var(--clear-no-play)/0.4)", color: "hsl(var(--muted-foreground))" },
  1: { borderColor: "hsl(var(--clear-failed)/0.6)", background: "hsl(var(--clear-failed)/0.15)", color: "hsl(var(--clear-failed))" },
  2: { borderColor: "hsl(var(--clear-assist)/0.6)", background: "hsl(var(--clear-assist)/0.2)", color: "hsl(var(--clear-assist))" },
  3: { borderColor: "hsl(var(--clear-easy)/0.6)", background: "hsl(var(--clear-easy)/0.2)", color: "hsl(var(--clear-easy))" },
  4: { borderColor: "hsl(var(--clear-normal)/0.6)", background: "hsl(var(--clear-normal)/0.2)", color: "hsl(var(--clear-normal))" },
  5: { borderColor: "hsl(var(--clear-hard)/0.6)", background: "hsl(var(--clear-hard)/0.2)", color: "hsl(var(--clear-hard))" },
  6: { borderColor: "hsl(var(--clear-exhard)/0.6)", background: "hsl(var(--clear-exhard)/0.2)", color: "hsl(var(--clear-exhard))" },
  7: { borderColor: "hsl(var(--clear-fc)/0.6)", background: "hsl(var(--clear-fc)/0.2)", color: "hsl(var(--clear-fc))" },
  8: { borderColor: "hsl(var(--clear-perfect)/0.6)", background: "hsl(var(--clear-perfect)/0.2)", color: "hsl(var(--clear-perfect))" },
  9: { borderColor: "hsl(var(--clear-max)/0.6)", background: "hsl(var(--clear-max)/0.2)", color: "hsl(var(--clear-max))" },
};

function getClientLabels(clientType: string) {
  if (clientType === "lr2") return LR2_CLEAR_TYPE_LABELS;
  if (clientType === "beatoraja") return BEATORAJA_CLEAR_TYPE_LABELS;
  return CLEAR_TYPE_LABELS;
}

export function clearBadge(clearType: number | null, clientType: string) {
  if (clearType === null) return null;
  const labels = getClientLabels(clientType);
  const label = labels[clearType] ?? String(clearType);
  const style = CLEAR_BADGE_STYLE[clearType] ?? CLEAR_BADGE_STYLE[0];
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium border shrink-0"
      style={style}
    >
      {label}
    </span>
  );
}

/** Get YYYY-MM-DD group key from a RecentUpdate entry. */
function getGroupKey(u: RecentUpdate): string {
  const ts = u.recorded_at ?? u.synced_at;
  return ts ? ts.slice(0, 10) : "unknown";
}

/** Format a YYYY-MM-DD date key as a Korean date label. */
function formatGroupLabel(dateKey: string): string {
  if (dateKey === "unknown") return "날짜 미상";
  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const yesterdayStr = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, "0")}-${String(yesterday.getDate()).padStart(2, "0")}`;

  const [, m, d] = dateKey.split("-");
  const base = `${Number(m)}월 ${Number(d)}일`;
  if (dateKey === todayStr) return `${base} (오늘)`;
  if (dateKey === yesterdayStr) return `${base} (어제)`;
  return base;
}

function isFirstClear(u: RecentUpdate): boolean {
  return (u.clear_type ?? 0) >= 3;
}

function formatElapsed(u: RecentUpdate): string {
  const ts = u.recorded_at ?? u.synced_at;
  if (!ts) return "";
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "방금 전";
  if (mins < 60) return `${mins}분 전`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}일 전`;
  const d = new Date(ts);
  return `${d.getMonth() + 1}월 ${d.getDate()}일`;
}

export function UpdateRow({ u }: { u: RecentUpdate }) {
  const [expanded, setExpanded] = useState(false);
  const labels = getClientLabels(u.client_type);
  const songName =
    u.title ??
    (u.fumen_sha256 ? u.fumen_sha256.slice(0, 8) + "…" : null) ??
    (u.fumen_md5 ? u.fumen_md5.slice(0, 8) + "…" : "(알 수 없음)");
  const rankChanged = u.rank !== null;
  const firstClear = isFirstClear(u);
  const elapsed = formatElapsed(u);

  return (
    <div
      className={`py-2 border-b border-border/40 last:border-0 cursor-pointer${firstClear ? " border-l-2 border-l-warning pl-2" : ""}`}
      onClick={() => setExpanded((prev) => !prev)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1 min-w-0">
          {/* First clear badge + song name + subtitle */}
          <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
            {firstClear && (
              <span
                className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium border shrink-0"
                style={{ borderColor: "hsl(var(--warning)/0.6)", background: "hsl(var(--warning)/0.15)", color: "hsl(var(--warning))" }}
              >
                ★ 첫 클리어
              </span>
            )}
            {clearBadge(u.clear_type, u.client_type)}
            {(u.fumen_sha256 || u.fumen_md5) ? (
              <Link
                href={`/songs/${u.fumen_sha256 || u.fumen_md5}`}
                className="text-xs font-medium truncate max-w-[200px] hover:text-primary transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                {songName}
              </Link>
            ) : (
              <span className="text-xs font-medium truncate max-w-[200px]">{songName}</span>
            )}
          </div>

          {/* Difficulty level badges */}
          {u.difficulty_levels.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              {u.difficulty_levels.map(({ symbol, level }, i) => (
                <span
                  key={i}
                  className="inline-flex items-center rounded px-1.5 py-0 text-[10px] font-medium border border-primary/40 text-primary bg-primary/10"
                >
                  {symbol}{level}
                </span>
              ))}
            </div>
          )}

          {/* Changes: rank, exscore */}
          <div className="flex gap-2 flex-wrap">
            {rankChanged && (
              <span className="text-[10px] text-muted-foreground">
                Rank: {u.rank}
              </span>
            )}
            {u.exscore !== null && (
              <span className="text-[10px] text-muted-foreground font-mono">
                EX: {u.exscore}
              </span>
            )}
          </div>
        </div>

        <div className="flex flex-col items-end gap-1 shrink-0">
          <div className="flex items-center gap-1">
            <span className="text-[10px] text-muted-foreground uppercase">{u.client_type}</span>
            {expanded ? (
              <ChevronUp className="h-3 w-3 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-3 w-3 text-muted-foreground" />
            )}
          </div>
          {elapsed && (
            <span className="text-[10px] text-muted-foreground">{elapsed}</span>
          )}
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-border/30 pt-2 mt-2 grid grid-cols-2 gap-x-4 gap-y-1">
          {u.min_bp !== null && (
            <span className="text-[10px] text-muted-foreground">
              BP: {u.min_bp}
            </span>
          )}
          {u.play_count !== null && (
            u.is_initial_sync ? (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="text-[10px] text-muted-foreground cursor-help">
                      플레이 수: - → {u.play_count}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent className="text-xs">
                    첫 동기화 — 이전 플레이 횟수 불명
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            ) : u.prev_play_count !== null ? (
              <span className="text-[10px] text-muted-foreground">
                플레이 수: {u.prev_play_count} → {u.play_count}
              </span>
            ) : (
              <span className="text-[10px] text-muted-foreground">
                플레이 수: {u.play_count}
              </span>
            )
          )}
          {u.rate !== null && (
            <span className="text-[10px] text-muted-foreground">
              스코어율: {u.rate.toFixed(1)}%
            </span>
          )}
          {u.artist && (
            <span className="text-[10px] text-muted-foreground truncate">
              {u.artist}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

interface Props {
  clientType?: ClientTypeFilter;
}

export function RecentActivity({ clientType = "all" }: Props) {
  const { data, isLoading } = useRecentUpdates(50, clientType);

  // Group by date key, preserving order
  const groups = useMemo(() => {
    if (!data?.updates.length) return [];
    const order: string[] = [];
    const map: Record<string, RecentUpdate[]> = {};
    for (const u of data.updates) {
      const key = getGroupKey(u);
      if (!map[key]) { order.push(key); map[key] = []; }
      map[key].push(u);
    }
    return order.map((key) => ({ key, label: formatGroupLabel(key), items: map[key] }));
  }, [data]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>최근 활동</CardTitle>
        <CardDescription>최근 스코어 갱신 이력</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="h-4 w-32 bg-muted rounded animate-pulse" />
                <div className="h-4 w-16 bg-muted rounded animate-pulse" />
              </div>
            ))}
          </div>
        )}

        {!isLoading && groups.length === 0 && (
          <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
            로컬 에이전트를 설치하고 동기화하면 활동 내역이 표시됩니다.
          </div>
        )}

        {!isLoading && groups.length > 0 && (
          <div className="space-y-4">
            {groups.map(({ key, label, items }) => (
              <div key={key}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-semibold text-muted-foreground">{label}</span>
                  <div className="flex items-center gap-1">
                    {(() => {
                      const updateCount = items.filter(u => !u.is_stat_only).length;
                      const playOnlyCount = items.filter(u => u.is_stat_only).length;
                      return (
                        <>
                          <span className="text-[10px] bg-muted rounded px-1.5 py-0.5" style={{ color: "hsl(var(--primary))" }}>
                            갱신 {updateCount}건
                          </span>
                          {playOnlyCount > 0 && (
                            <span className="text-[10px] bg-muted rounded px-1.5 py-0.5" style={{ color: "hsl(var(--chart-play))" }}>
                              플레이 {playOnlyCount}건
                            </span>
                          )}
                        </>
                      );
                    })()}
                  </div>
                </div>
                <div>
                  {items.map((u) => <UpdateRow key={u.id} u={u} />)}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
