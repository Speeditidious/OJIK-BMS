"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, RefreshCw, Music } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { DifficultyTableDetail, TableFumen, TableFumenScore } from "@/types";
import { clearBadge } from "@/components/dashboard/RecentActivity";

interface TableDetailProps {
  tableId: string;
  isLoggedIn: boolean;
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
              <div>Clear: {source_client_detail.clear_type}</div>
            )}
            {source_client_detail.exscore && (
              <div>EX: {source_client_detail.exscore}</div>
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

export function TableDetail({ tableId, isLoggedIn }: TableDetailProps) {
  const [selectedLevel, setSelectedLevel] = useState<string | null>(null);
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

  const hasData = table.level_order.length > 0;
  const songsByLevel = songs?.reduce<Record<string, TableFumen[]>>((acc, song) => {
    if (!acc[song.level]) acc[song.level] = [];
    acc[song.level].push(song);
    return acc;
  }, {}) ?? {};

  const displayedSongs = selectedLevel
    ? (songsByLevel[selectedLevel] ?? [])
    : songs ?? [];

  // Show user score columns only when logged in and at least one song has scores
  const hasUserScores = isLoggedIn && displayedSongs.some((s) => s.user_score !== null);

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
                원본 <ExternalLink className="h-3 w-3" />
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
          <div className="w-32 shrink-0 border-r overflow-y-auto">
            <div
              className={cn(
                "px-3 py-2 text-sm cursor-pointer transition-colors",
                selectedLevel === null
                  ? "bg-primary/10 text-primary font-medium"
                  : "hover:bg-secondary text-muted-foreground"
              )}
              onClick={() => setSelectedLevel(null)}
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
                  onClick={() => setSelectedLevel(level)}
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
              <ScrollArea className="h-full">
                {/* Column header (only when user scores are available) */}
                {hasUserScores && (
                  <div className="sticky top-0 z-10 bg-background border-b px-4 py-1.5 flex items-center gap-2 text-[10px] text-muted-foreground font-medium">
                    <span className="w-10 shrink-0">레벨</span>
                    <span className="flex-1 min-w-0">곡명 / 아티스트</span>
                    <span className="w-16 text-center">클리어</span>
                    <span className="w-14 text-center">EX</span>
                    <span className="w-14 text-center">Rate</span>
                    <span className="w-10 text-center">Rank</span>
                    <span className="w-12 text-center">BP</span>
                    <span className="w-10 text-center">출처</span>
                    <span className="w-5 shrink-0" />
                  </div>
                )}
                <div className="divide-y divide-border/50">
                  {displayedSongs.map((song, i) => {
                    const levelLabel = `${table.symbol ?? ""}${song.level.replace(table.symbol ?? "", "")}`;
                    const s = song.user_score;
                    return (
                      <div key={`${song.md5}-${song.sha256}-${i}`} className="px-4 py-2.5 hover:bg-secondary/50 transition-colors">
                        <div className="flex items-center gap-2">
                          {/* Level badge */}
                          <Badge variant="outline" className="font-mono text-xs shrink-0 px-1.5 py-0 w-10 justify-center">
                            {levelLabel}
                          </Badge>

                          {/* Title & Artist */}
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">{song.title || "(제목 없음)"}</p>
                            <p className="text-xs text-muted-foreground truncate">{song.artist}</p>
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

                          {/* Download link */}
                          {song.file_url ? (
                            <a
                              href={song.file_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="shrink-0 text-muted-foreground hover:text-foreground"
                              title="다운로드 페이지"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                          ) : (
                            <span className="w-5 shrink-0" />
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </ScrollArea>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
