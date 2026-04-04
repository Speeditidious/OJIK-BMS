"use client";

import {
  DndContext,
  DragEndEvent,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { GripVertical, Plus, Star, StarOff } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { DifficultyTable } from "@/types";

interface TableSidebarProps {
  favorites: DifficultyTable[];
  allTables: DifficultyTable[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onImportClick: () => void;
  isLoggedIn: boolean;
}

interface SortableTableRowProps {
  table: DifficultyTable;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onToggleFavorite: (table: DifficultyTable, e: React.MouseEvent) => void;
  isLoggedIn: boolean;
}

function SortableTableRow({
  table,
  selectedId,
  onSelect,
  onToggleFavorite,
  isLoggedIn,
}: SortableTableRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: table.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      onClick={() => onSelect(table.id)}
      className={cn(
        "flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer",
        selectedId === table.id
          ? "bg-primary/10 text-primary"
          : "text-foreground"
      )}
    >
      <button
        {...attributes}
        {...listeners}
        onClick={(e) => e.stopPropagation()}
        className="shrink-0 opacity-40 hover:opacity-80 transition-opacity cursor-grab active:cursor-grabbing"
        title="순서 변경"
      >
        <GripVertical className="h-3.5 w-3.5 text-muted-foreground" />
      </button>
      <div className="flex-1 flex items-center gap-2 min-w-0 hover:text-primary transition-colors">
        {table.symbol && (
          <Badge variant="outline" className="shrink-0 text-label font-mono px-1.5 py-0">
            {table.symbol}
          </Badge>
        )}
        <span className="truncate text-body">{table.name}</span>
        {table.song_count != null && (
          <span className="text-label text-muted-foreground shrink-0">{table.song_count}</span>
        )}
      </div>
      {isLoggedIn && (
        <button
          onClick={(e) => onToggleFavorite(table, e)}
          className="shrink-0 text-muted-foreground hover:text-destructive transition-colors"
          title="즐겨찾기 해제"
        >
          <StarOff className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

function StaticTableRow({
  table,
  selectedId,
  onSelect,
  onToggleFavorite,
  isLoggedIn,
}: {
  table: DifficultyTable;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onToggleFavorite: (table: DifficultyTable, e: React.MouseEvent) => void;
  isLoggedIn: boolean;
}) {
  return (
    <div
      key={table.id}
      onClick={() => onSelect(table.id)}
      className={cn(
        "flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer",
        selectedId === table.id
          ? "bg-primary/10 text-primary"
          : "text-foreground"
      )}
    >
      <div className="flex-1 flex items-center gap-2 min-w-0 hover:text-primary transition-colors">
        {table.symbol && (
          <Badge variant="outline" className="shrink-0 text-label font-mono px-1.5 py-0">
            {table.symbol}
          </Badge>
        )}
        <span className="truncate text-body">{table.name}</span>
      </div>
      {isLoggedIn && (
        <button
          onClick={(e) => onToggleFavorite(table, e)}
          className="shrink-0 text-muted-foreground hover:text-yellow-400 transition-colors"
          title="즐겨찾기 추가"
        >
          <Star className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
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

  // Local optimistic state for favorites order during drag
  const [localFavorites, setLocalFavorites] = useState<DifficultyTable[] | null>(null);
  const displayedFavorites = localFavorites ?? favorites;

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const addFav = useMutation({
    mutationFn: (id: string) => api.post(`/tables/favorites/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tables", "favorites"] });
    },
  });

  const removeFav = useMutation({
    mutationFn: (id: string) => api.delete(`/tables/favorites/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tables", "favorites"] });
    },
  });

  const reorder = useMutation({
    mutationFn: (tableIds: string[]) =>
      api.put("/tables/favorites/reorder", { table_ids: tableIds }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tables", "favorites"] });
      setLocalFavorites(null);
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

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const current = localFavorites ?? favorites;
    const oldIndex = current.findIndex((t) => t.id === active.id);
    const newIndex = current.findIndex((t) => t.id === over.id);
    if (oldIndex === -1 || newIndex === -1) return;

    const reordered = arrayMove(current, oldIndex, newIndex);
    setLocalFavorites(reordered);
    reorder.mutate(reordered.map((t) => t.id));
  };

  const otherTables = allTables.filter((t) => !favoriteIds.has(t.id));

  return (
    <div className="flex flex-col h-full border-r">
      <div className="px-4 py-3 flex items-center justify-between border-b">
        <span className="text-body font-semibold text-muted-foreground uppercase tracking-wide">
          난이도표
        </span>
        {isLoggedIn && (
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onImportClick} title="외부 난이도표 추가">
            <Plus className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Single scrollable area with hidden scrollbar */}
      <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-2 py-2 [&::-webkit-scrollbar]:hidden">
        {/* Favorites section */}
        {isLoggedIn && displayedFavorites.length > 0 && (
          <>
            <p className="px-2 pb-1 text-label text-muted-foreground font-medium">즐겨찾기</p>
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext items={displayedFavorites.map((t) => t.id)} strategy={verticalListSortingStrategy}>
                {displayedFavorites.map((t) => (
                  <SortableTableRow
                    key={t.id}
                    table={t}
                    selectedId={selectedId}
                    onSelect={onSelect}
                    onToggleFavorite={toggleFavorite}
                    isLoggedIn={isLoggedIn}
                  />
                ))}
              </SortableContext>
            </DndContext>
            {otherTables.length > 0 && <Separator className="my-2" />}
          </>
        )}

        {/* 전체 section */}
        {otherTables.length > 0 && (
          <>
            {isLoggedIn && displayedFavorites.length > 0 && (
              <p className="px-2 pb-1 text-label text-muted-foreground font-medium">전체</p>
            )}
            {otherTables.map((t) => (
              <StaticTableRow
                key={t.id}
                table={t}
                selectedId={selectedId}
                onSelect={onSelect}
                onToggleFavorite={toggleFavorite}
                isLoggedIn={isLoggedIn}
              />
            ))}
          </>
        )}

        {allTables.length === 0 && (
          <p className="px-2 py-4 text-body text-muted-foreground text-center">
            난이도표 데이터를 불러오는 중...
          </p>
        )}
      </div>
    </div>
  );
}
