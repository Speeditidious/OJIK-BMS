"use client";

import { useMemo } from "react";
import { useRecentUpdates, RecentUpdate, ClientTypeFilter } from "@/hooks/use-analysis";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  CLEAR_TYPE_LABELS,
  LR2_CLEAR_TYPE_LABELS,
  BEATORAJA_CLEAR_TYPE_LABELS,
} from "@/components/charts/ClearDistributionChart";

// CSS variable refs per internal clear_type (0=NO PLAY, 1=FAILED, 2=ASSIST, 3=EASY, 4=NORMAL, 5=HARD, 6=EXHARD, 7=FC)
const CLEAR_BADGE_STYLE: Record<number, React.CSSProperties> = {
  0: { borderColor: "hsl(var(--clear-no-play))", background: "hsl(var(--clear-no-play)/0.4)", color: "hsl(var(--muted-foreground))" },
  1: { borderColor: "hsl(var(--clear-failed)/0.6)", background: "hsl(var(--clear-failed)/0.15)", color: "hsl(var(--clear-failed))" },
  2: { borderColor: "hsl(var(--clear-assist)/0.6)", background: "hsl(var(--clear-assist)/0.2)", color: "hsl(var(--clear-assist))" },
  3: { borderColor: "hsl(var(--clear-easy)/0.6)", background: "hsl(var(--clear-easy)/0.2)", color: "hsl(var(--clear-easy))" },
  4: { borderColor: "hsl(var(--clear-normal)/0.6)", background: "hsl(var(--clear-normal)/0.2)", color: "hsl(var(--clear-normal))" },
  5: { borderColor: "hsl(var(--clear-hard)/0.6)", background: "hsl(var(--clear-hard)/0.2)", color: "hsl(var(--clear-hard))" },
  6: { borderColor: "hsl(var(--clear-exhard)/0.6)", background: "hsl(var(--clear-exhard)/0.2)", color: "hsl(var(--clear-exhard))" },
  7: { borderColor: "hsl(var(--clear-fc)/0.6)", background: "hsl(var(--clear-fc)/0.2)", color: "hsl(var(--clear-fc))" },
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

/** Convert score_rate (0–1 float) to rank letter per BMS convention. */
export function getRank(scoreRate: number | null): string {
  if (scoreRate === null) return "–";
  if (scoreRate >= 1.0) return "MAX";
  if (scoreRate >= 8 / 9) return "AAA";
  if (scoreRate >= 7 / 9) return "AA";
  if (scoreRate >= 6 / 9) return "A";
  if (scoreRate >= 5 / 9) return "B";
  if (scoreRate >= 4 / 9) return "C";
  if (scoreRate >= 3 / 9) return "D";
  if (scoreRate >= 2 / 9) return "E";
  return "F";
}

/** Get YYYY-MM-DD group key from a RecentUpdate entry. */
function getGroupKey(u: RecentUpdate): string {
  const ts = u.played_at ?? u.sync_date ?? u.recorded_at;
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

export function UpdateRow({ u }: { u: RecentUpdate }) {
  const labels = getClientLabels(u.client_type);
  const songName =
    u.title ??
    (u.song_sha256 ? u.song_sha256.slice(0, 8) + "…" : null) ??
    (u.song_md5 ? u.song_md5.slice(0, 8) + "…" : "(알 수 없음)");
  const clearChanged =
    u.old_clear_type !== null && u.clear_type !== null && u.clear_type !== u.old_clear_type;
  const scoreChanged = u.score !== null && u.old_score !== null && u.score !== u.old_score;
  const rankChanged =
    u.score_rate !== null &&
    u.old_score_rate !== null &&
    getRank(u.score_rate) !== getRank(u.old_score_rate);

  return (
    <div className="flex items-start justify-between py-2 border-b border-border/40 last:border-0 gap-2">
      <div className="flex flex-col gap-1 min-w-0">
        {/* Song name + subtitle */}
        <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
          {clearBadge(u.clear_type, u.client_type)}
          <span className="text-xs font-medium truncate max-w-[200px]">{songName}</span>
          {u.subtitle && (
            <span className="text-[10px] text-muted-foreground truncate max-w-[120px]">
              {u.subtitle}
            </span>
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

        {/* Changes: clear type, rank, score */}
        <div className="flex gap-2 flex-wrap">
          {clearChanged && (
            <span className="text-[10px] text-muted-foreground">
              {labels[u.old_clear_type!]} → {labels[u.clear_type!]}
            </span>
          )}
          {rankChanged && (
            <span className="text-[10px] text-muted-foreground">
              Rank: {getRank(u.old_score_rate)} → {getRank(u.score_rate)}
            </span>
          )}
          {scoreChanged && (
            <span className="text-[10px] text-muted-foreground font-mono">
              {u.old_score?.toFixed(0)} → {u.score?.toFixed(0)}
            </span>
          )}
        </div>
      </div>

      <div className="flex flex-col items-end gap-1 shrink-0">
        <span className="text-[10px] text-muted-foreground uppercase">{u.client_type}</span>
      </div>
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
                  <span className="text-[10px] text-muted-foreground bg-muted rounded px-1.5 py-0.5">
                    {items.length}건
                  </span>
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
