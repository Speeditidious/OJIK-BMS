"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, RefreshCw, Music } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { DifficultyTableDetail, TableSong } from "@/types";

interface TableDetailProps {
  tableId: number;
  isLoggedIn: boolean;
}

export function TableDetail({ tableId, isLoggedIn }: TableDetailProps) {
  const [selectedLevel, setSelectedLevel] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: table, isLoading: tableLoading } = useQuery<DifficultyTableDetail>({
    queryKey: ["table", tableId],
    queryFn: () => api.get(`/tables/${tableId}`),
    staleTime: 5 * 60 * 1000,
  });

  const { data: songs, isLoading: songsLoading } = useQuery<TableSong[]>({
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
  const songsByLevel = songs?.reduce<Record<string, TableSong[]>>((acc, song) => {
    if (!acc[song.level]) acc[song.level] = [];
    acc[song.level].push(song);
    return acc;
  }, {}) ?? {};

  const displayedSongs = selectedLevel
    ? (songsByLevel[selectedLevel] ?? [])
    : songs ?? [];

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
            {table.last_synced_at && (
              <span>마지막 동기화: {new Date(table.last_synced_at).toLocaleDateString("ko-KR")}</span>
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
                <div className="divide-y divide-border/50">
                  {displayedSongs.map((song, i) => (
                    <div key={`${song.md5}-${i}`} className="px-4 py-2.5 hover:bg-secondary/50 transition-colors">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="font-mono text-xs shrink-0 px-1.5 py-0">
                          {song.level}
                        </Badge>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{song.title || "(제목 없음)"}</p>
                          <p className="text-xs text-muted-foreground truncate">{song.artist}</p>
                        </div>
                        {song.url && (
                          <a
                            href={song.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="shrink-0 text-muted-foreground hover:text-foreground"
                            title="다운로드 페이지"
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
