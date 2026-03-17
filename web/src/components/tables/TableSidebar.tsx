"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Star, StarOff, RefreshCw, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { DifficultyTable } from "@/types";

interface TableSidebarProps {
  favorites: DifficultyTable[];
  allTables: DifficultyTable[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onImportClick: () => void;
  isLoggedIn: boolean;
}

export function TableSidebar({
  favorites,
  allTables,
  selectedId,
  onSelect,
  onImportClick,
  isLoggedIn,
}: TableSidebarProps) {
  const queryClient = useQueryClient();
  const favoriteIds = new Set(favorites.map((t) => t.id));

  const addFav = useMutation({
    mutationFn: (id: number) => api.post(`/tables/favorites/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["favorites"] });
    },
  });

  const removeFav = useMutation({
    mutationFn: (id: number) => api.delete(`/tables/favorites/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["favorites"] });
    },
  });

  const toggleFavorite = (table: DifficultyTable, e: React.MouseEvent) => {
    e.stopPropagation();
    if (favoriteIds.has(table.id)) {
      removeFav.mutate(table.id);
    } else {
      addFav.mutate(table.id);
    }
  };

  // Non-favorite tables (all tables not in favorites)
  const otherTables = allTables.filter((t) => !favoriteIds.has(t.id));

  const renderTableRow = (table: DifficultyTable, isFav: boolean) => (
    <div
      key={table.id}
      onClick={() => onSelect(table.id)}
      className={cn(
        "group flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer transition-colors",
        selectedId === table.id
          ? "bg-primary/10 text-primary"
          : "hover:bg-secondary text-foreground"
      )}
    >
      {table.symbol && (
        <Badge variant="outline" className="shrink-0 text-xs font-mono px-1.5 py-0">
          {table.symbol}
        </Badge>
      )}
      <span className="flex-1 truncate text-sm">{table.name}</span>
      {table.song_count != null && (
        <span className="text-xs text-muted-foreground shrink-0">{table.song_count}</span>
      )}
      {isLoggedIn && (
        <button
          onClick={(e) => toggleFavorite(table, e)}
          className={cn(
            "shrink-0 opacity-0 group-hover:opacity-100 transition-opacity",
            isFav && "opacity-60"
          )}
          title={isFav ? "즐겨찾기 해제" : "즐겨찾기 추가"}
        >
          {isFav ? (
            <StarOff className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <Star className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </button>
      )}
    </div>
  );

  return (
    <div className="flex flex-col h-full border-r">
      <div className="px-4 py-3 flex items-center justify-between border-b">
        <span className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
          난이도표
        </span>
        {isLoggedIn && (
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onImportClick} title="외부 난이도표 추가">
            <Plus className="h-4 w-4" />
          </Button>
        )}
      </div>

      <ScrollArea className="flex-1 px-2 py-2">
        {isLoggedIn && favorites.length > 0 && (
          <>
            <p className="px-2 pb-1 text-xs text-muted-foreground font-medium">즐겨찾기</p>
            {favorites.map((t) => renderTableRow(t, true))}
            {otherTables.length > 0 && <Separator className="my-2" />}
          </>
        )}

        {otherTables.length > 0 && (
          <>
            {isLoggedIn && favorites.length > 0 && (
              <p className="px-2 pb-1 text-xs text-muted-foreground font-medium">전체</p>
            )}
            {otherTables.map((t) => renderTableRow(t, false))}
          </>
        )}

        {allTables.length === 0 && (
          <p className="px-2 py-4 text-sm text-muted-foreground text-center">
            난이도표 데이터를 불러오는 중...
          </p>
        )}
      </ScrollArea>
    </div>
  );
}
