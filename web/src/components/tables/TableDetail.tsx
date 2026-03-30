"use client";

import { useMemo, useRef, memo, useCallback } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ExternalLink, RefreshCw, Music, Package, FileCode, Youtube } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { compareTitles } from "@/lib/bms-sort";
import { formatBpm, formatNotes, formatLength } from "@/lib/bms-format";
import type { DifficultyTableDetail, TableFumen, TableFumenScore } from "@/types";
import { clearBadge } from "@/components/dashboard/RecentActivity";

interface TableDetailProps {
  tableId: string;
  isLoggedIn: boolean;
  selectedLevel: string | null;
  onLevelChange: (level: string | null) => void;
}

// Source client label display
function SourceClientBadge({ score }: { score: TableFumenScore }) {
  const { source_client, source_client_detail } = score;
  if (!source_client) return null;

  const badge = (
    <span className="text-[10px] font-mono px-1 py-0.5 rounded border border-border/60 text-muted-foreground">
      {source_client}
    </span>
  );

  if (source_client !== "MIX" || !source_client_detail) return badge;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>{badge}</TooltipTrigger>
        <TooltipContent side="left" className="text-xs">
          <div className="space-y-0.5">
            {source_client_detail.clear_type && (
              <div>Lamp: {source_client_detail.clear_type}</div>
            )}
            {source_client_detail.exscore && (
              <div>Score: {source_client_detail.exscore}</div>
            )}
            {source_client_detail.min_bp && (
              <div>BP: {source_client_detail.min_bp}</div>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function songHash(song: TableFumen): string {
  return song.sha256 || song.md5 || "";
}

export function TableDetail({ tableId, isLoggedIn, selectedLevel, onLevelChange }: TableDetailProps) {
  const queryClient = useQueryClient();

  const { data: table, isLoading: tableLoading } = useQuery<DifficultyTableDetail>({
    queryKey: ["table", tableId],
    queryFn: () => api.get(`/tables/${tableId}`),
    staleTime: 5 * 60 * 1000,
  });

  const { data: songs, isLoading: songsLoading } = useQuery<TableFumen[]>({
    queryKey: ["table-songs", tableId, selectedLevel],
    queryFn: () => {
      const qs = selectedLevel ? `?level=${encodeURIComponent(selectedLevel)}` : "";
      return api.get(`/tables/${tableId}/songs${qs}`);
    },
    enabled: selectedLevel !== null || (!!table && table.level_order.length > 0),
    staleTime: 5 * 60 * 1000,
  });

  const syncMutation = useMutation({
    mutationFn: () => api.post(`/tables/${tableId}/sync`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tables"] });
      queryClient.invalidateQueries({ queryKey: ["table", tableId] });
      queryClient.invalidateQueries({ queryKey: ["table-songs", tableId] });
    },
  });

  const hasData = (table?.level_order.length ?? 0) > 0;

  const songsByLevel = useMemo(
    () =>
      songs?.reduce<Record<string, TableFumen[]>>((acc, song) => {
        if (!acc[song.level]) acc[song.level] = [];
        acc[song.level].push(song);
        return acc;
      }, {}) ?? {},
    [songs]
  );

  const levelOrderIndex = useMemo(
    () => Object.fromEntries((table?.level_order ?? []).map((l, i) => [l, i])),
    [table?.level_order]
  );

  const displayedSongs = useMemo(() => {
    const base = selectedLevel
      ? (songsByLevel[selectedLevel] ?? [])
      : songs ?? [];
    return base.slice().sort((a, b) => {
      const ai = levelOrderIndex[a.level] ?? 9999;
      const bi = levelOrderIndex[b.level] ?? 9999;
      if (ai !== bi) return ai - bi;
      return compareTitles(a.title ?? "", b.title ?? "");
    });
  }, [selectedLevel, songsByLevel, songs, levelOrderIndex]);

  const hasUserScores = useMemo(
    () => isLoggedIn && displayedSongs.some((s) => s.user_score !== null),
    [isLoggedIn, displayedSongs]
  );

  // Early returns after all hooks
  if (tableLoading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        불러오는 중...
      </div>
    );
  }

  if (!table) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        난이도표를 찾을 수 없습니다.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b flex items-start gap-3 shrink-0">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {table.symbol && (
              <Badge variant="secondary" className="font-mono text-sm">
                {table.symbol}
              </Badge>
            )}
            <h2 className="text-xl font-bold truncate">{table.name}</h2>
          </div>
          <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
            {table.song_count != null && (
              <span>{table.song_count.toLocaleString()}곡</span>
            )}
            {table.updated_at && (
              <span>마지막 동기화: {new Date(table.updated_at).toLocaleDateString("ko-KR")}</span>
            )}
            {table.source_url && (
              <a
                href={table.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 hover:text-foreground transition-colors"
              >
                난이도표 링크 <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </div>
        {isLoggedIn && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            title="수동 동기화"
          >
            <RefreshCw className={cn("h-4 w-4", syncMutation.isPending && "animate-spin")} />
          </Button>
        )}
      </div>

      {!hasData ? (
        <div className="flex flex-col items-center justify-center flex-1 gap-3 text-muted-foreground">
          <Music className="h-12 w-12 opacity-30" />
          <p className="text-sm">난이도표 데이터가 아직 없습니다.</p>
          {isLoggedIn && (
            <Button variant="outline" size="sm" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>
              <RefreshCw className={cn("h-4 w-4 mr-2", syncMutation.isPending && "animate-spin")} />
              지금 동기화
            </Button>
          )}
        </div>
      ) : (
        <div className="flex flex-1 overflow-hidden">
          {/* Level selector */}
          <div className="w-32 shrink-0 border-r overflow-y-auto overscroll-contain [&::-webkit-scrollbar]:hidden">
            <div
              className={cn(
                "px-3 py-2 text-sm cursor-pointer transition-colors",
                selectedLevel === null
                  ? "bg-primary/10 text-primary font-medium"
                  : "hover:bg-secondary text-muted-foreground"
              )}
              onClick={() => onLevelChange(null)}
            >
              전체
            </div>
            {table.level_order.map((level) => {
              const count = songsByLevel[level]?.length;
              return (
                <div
                  key={level}
                  className={cn(
                    "px-3 py-2 text-sm cursor-pointer transition-colors flex items-center justify-between",
                    selectedLevel === level
                      ? "bg-primary/10 text-primary font-medium"
                      : "hover:bg-secondary text-muted-foreground"
                  )}
                  onClick={() => onLevelChange(level)}
                >
                  <span className="font-mono">
                    {table.symbol}{level.replace(table.symbol ?? "", "")}
                  </span>
                  {count != null && (
                    <span className="text-xs opacity-60">{count}</span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Song list */}
          <div className="flex-1 overflow-hidden">
            {songsLoading ? (
              <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                불러오는 중...
              </div>
            ) : displayedSongs.length === 0 ? (
              <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                곡이 없습니다.
              </div>
            ) : (
              <SongVirtualList
                songs={displayedSongs}
                table={table}
                hasUserScores={hasUserScores}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// --- Virtualized song list ---

interface SongVirtualListProps {
  songs: TableFumen[];
  table: DifficultyTableDetail;
  hasUserScores: boolean;
}

const SongVirtualList = memo(function SongVirtualList({ songs, table, hasUserScores }: SongVirtualListProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  // eslint-disable-next-line react-hooks/incompatible-library
  const rowVirtualizer = useVirtualizer({
    count: songs.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 44,
    overscan: 10,
  });

  return (
    <div ref={parentRef} className="[&::-webkit-scrollbar]:hidden" style={{ height: "100%", overflowY: "auto", overscrollBehavior: "contain" }}>
      {/* Sticky column header */}
      <div
        className="sticky top-0 z-10 bg-background border-b px-4 py-1.5 flex items-center gap-2 text-[10px] text-muted-foreground font-medium"
        style={{ minWidth: 680 }}
      >
        <span className="w-10 shrink-0">Level</span>
        <span className="flex-1 min-w-[140px]">Title / Artist</span>
        {hasUserScores && (
          <>
            <span className="w-16 text-center">Lamp</span>
            <span className="w-14 text-center">Score</span>
            <span className="w-14 text-center">Rate</span>
            <span className="w-10 text-center">Rank</span>
            <span className="w-12 text-center">BP</span>
            <span className="w-10 text-center">Env</span>
          </>
        )}
        <span className="w-20 text-center">BPM</span>
        <span className="w-14 text-center">Notes</span>
        <span className="w-12 text-center">Length</span>
        <span className="w-8 shrink-0 text-center">URL1</span>
        <span className="w-8 shrink-0 text-center">URL2</span>
        <span className="w-8 shrink-0 text-center">Youtube</span>
      </div>

      {/* Virtualized rows container */}
      <div
        style={{
          height: rowVirtualizer.getTotalSize(),
          width: "100%",
          position: "relative",
        }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const song = songs[virtualRow.index];
          const levelLabel = `${table.symbol ?? ""}${song.level.replace(table.symbol ?? "", "")}`;
          const s = song.user_score;
          const hash = songHash(song);
          const { total: notesTotal, detail: notesDetail } = formatNotes(
            song.notes_total, song.notes_n, song.notes_ln, song.notes_s, song.notes_ls
          );

          return (
            <div
              key={virtualRow.key}
              style={{
                position: "absolute",
                top: virtualRow.start,
                left: 0,
                width: "100%",
                height: virtualRow.size,
                minWidth: 680,
              }}
              className="px-4 flex items-center gap-2 hover:bg-secondary/50 transition-colors border-b border-border/30"
            >
              {/* Level badge */}
              <Badge variant="outline" className="font-mono text-xs shrink-0 px-1.5 py-0 w-10 justify-center">
                {levelLabel}
              </Badge>

              {/* Title & Artist */}
              <div className="flex-1 min-w-[140px] min-w-0 overflow-hidden">
                {hash ? (
                  <Link
                    href={`/songs/${hash}`}
                    className="text-sm font-medium truncate hover:text-primary transition-colors block"
                  >
                    {song.title || "(제목 없음)"}
                  </Link>
                ) : (
                  <p className="text-sm font-medium truncate">{song.title || "(제목 없음)"}</p>
                )}
                <p className="text-xs text-muted-foreground truncate">{song.artist}</p>
                {song.user_tags.length > 0 && (
                  <div className="flex gap-1 flex-wrap">
                    {song.user_tags.map((t) => (
                      <span
                        key={t.id}
                        className="text-[10px] px-1.5 py-0 rounded-full border border-primary/30 text-primary/80 bg-primary/10"
                      >
                        {t.tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* User score columns */}
              {hasUserScores && (
                <>
                  <div className="w-16 flex justify-center">
                    {s ? clearBadge(s.best_clear_type, "") : (
                      <span className="text-xs text-muted-foreground">-</span>
                    )}
                  </div>
                  <div className="w-14 text-center text-xs text-muted-foreground">
                    {s?.best_exscore ?? "-"}
                  </div>
                  <div className="w-14 text-center text-xs text-muted-foreground">
                    {s?.rate != null ? `${s.rate.toFixed(2)}%` : "-"}
                  </div>
                  <div className="w-10 text-center text-xs font-mono text-muted-foreground">
                    {s?.rank ?? "-"}
                  </div>
                  <div className="w-12 text-center text-xs text-muted-foreground">
                    {s?.best_min_bp ?? "-"}
                  </div>
                  <div className="w-10 flex justify-center">
                    {s ? <SourceClientBadge score={s} /> : (
                      <span className="text-xs text-muted-foreground">-</span>
                    )}
                  </div>
                </>
              )}

              {/* BPM */}
              <div className="w-20 text-center text-xs text-muted-foreground font-mono">
                {formatBpm(song.bpm_main, song.bpm_min, song.bpm_max)}
              </div>

              {/* Notes */}
              <div className="w-14 text-center text-xs text-muted-foreground font-mono">
                {notesTotal === "-" ? "-" : (
                  notesDetail ? (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="cursor-help inline-flex items-center gap-0.5">
                            {notesTotal}
                            <span className="text-[8px] text-accent/70 leading-none">●</span>
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="left" className="text-xs font-mono">
                          <div className="space-y-0.5">
                            {notesDetail.split(" ").map((part) => {
                              const [label, val] = part.split(":");
                              return (
                                <div key={label} className="flex gap-2 justify-between">
                                  <span className="text-muted-foreground">{label}</span>
                                  <span>{val}</span>
                                </div>
                              );
                            })}
                          </div>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  ) : notesTotal
                )}
              </div>

              {/* Length */}
              <div className="w-12 text-center text-xs text-muted-foreground font-mono">
                {formatLength(song.length)}
              </div>

              {/* URL1 (file_url) */}
              <div className="w-8 flex justify-center shrink-0">
                {song.file_url ? (
                  <a
                    href={song.file_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-muted-foreground hover:text-foreground transition-colors"
                    title="URL1"
                  >
                    <Package className="h-3.5 w-3.5" />
                  </a>
                ) : (
                  <span className="text-muted-foreground/30 text-xs">–</span>
                )}
              </div>

              {/* URL2 (file_url_diff) */}
              <div className="w-8 flex justify-center shrink-0">
                {song.file_url_diff ? (
                  <a
                    href={song.file_url_diff}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-muted-foreground hover:text-foreground transition-colors"
                    title="URL2"
                  >
                    <FileCode className="h-3.5 w-3.5" />
                  </a>
                ) : (
                  <span className="text-muted-foreground/30 text-xs">–</span>
                )}
              </div>

              {/* Youtube */}
              <div className="w-8 flex justify-center shrink-0">
                {song.youtube_url ? (
                  <a
                    href={song.youtube_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[hsl(var(--destructive)/0.7)] hover:text-[hsl(var(--destructive))] transition-colors"
                    title="Youtube"
                  >
                    <Youtube className="h-3.5 w-3.5" />
                  </a>
                ) : (
                  <span className="text-muted-foreground/30 text-xs">–</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
});
