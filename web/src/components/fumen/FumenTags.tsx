"use client";

import { useState, useRef, useEffect } from "react";
import { X, Plus, GripVertical } from "lucide-react";
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
  horizontalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useFumenTags, useMyTags, useAddFumenTag, useDeleteFumenTag, useReorderFumenTags } from "@/hooks/use-fumen-tags";

// Deterministic pastel hue from tag string
function tagHue(tag: string): number {
  let hash = 0;
  for (const ch of tag) hash = (hash * 31 + ch.charCodeAt(0)) & 0xffff;
  return hash % 360;
}

function tagStyle(tag: string): React.CSSProperties {
  const hue = tagHue(tag);
  return {
    background: `hsl(${hue} 55% 70% / 0.2)`,
    borderColor: `hsl(${hue} 55% 70% / 0.5)`,
    color: `hsl(${hue} 55% 75%)`,
  };
}

function SortableTagPill({
  tag,
  onDelete,
}: {
  tag: { id: string; tag: string };
  onDelete: (id: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: tag.id });

  return (
    <span
      ref={setNodeRef}
      style={{
        ...tagStyle(tag.tag),
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        cursor: isDragging ? "grabbing" : undefined,
      }}
      className="inline-flex items-center gap-0.5 rounded-full pl-1.5 pr-2 py-0.5 text-label font-medium border select-none"
    >
      {/* 드래그 핸들 */}
      <button
        {...attributes}
        {...listeners}
        className="opacity-40 hover:opacity-80 transition-opacity cursor-grab active:cursor-grabbing p-0.5"
        tabIndex={-1}
        aria-label="순서 변경"
      >
        <GripVertical className="h-3 w-3" />
      </button>
      {tag.tag}
      <button
        onClick={() => onDelete(tag.id)}
        className="ml-0.5 opacity-60 hover:opacity-100 transition-opacity"
        aria-label={`태그 삭제: ${tag.tag}`}
      >
        <X className="h-3 w-3" />
      </button>
    </span>
  );
}

interface FumenTagsProps {
  hash: string;
}

export function FumenTags({ hash }: FumenTagsProps) {
  const { data: serverTags = [] } = useFumenTags(hash);
  const { data: myTags = [] } = useMyTags();
  const addTag = useAddFumenTag(hash);
  const deleteTag = useDeleteFumenTag(hash);
  const reorderTags = useReorderFumenTags(hash);

  // 낙관적 순서 상태 (드래그 중 즉시 반영)
  const [optimisticOrder, setOptimisticOrder] = useState<string[] | null>(null);
  const tags = optimisticOrder
    ? optimisticOrder.map(id => serverTags.find(t => t.id === id)).filter(Boolean)
    : serverTags;

  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setOpen(false);
        setInput("");
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const current = tags;
    const oldIdx = current.findIndex((t) => t!.id === active.id);
    const newIdx = current.findIndex((t) => t!.id === over.id);
    if (oldIdx === -1 || newIdx === -1) return;

    const reordered = arrayMove(current, oldIdx, newIdx);
    setOptimisticOrder(reordered.map((t) => t!.id));
    reorderTags.mutate(reordered.map((t) => t!.id), {
      onSuccess: () => setOptimisticOrder(null),
    });
  };

  const existingTagTexts = new Set(tags.map((t) => t!.tag));
  const suggestions = myTags.filter(
    (t) =>
      !existingTagTexts.has(t) &&
      (input === "" || t.toLowerCase().includes(input.toLowerCase()))
  );

  const handleSelect = (tag: string) => {
    const trimmed = tag.trim();
    if (!trimmed) return;
    addTag.mutate(trimmed, {
      onSuccess: () => {
        setInput("");
        inputRef.current?.focus();
      },
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (input.trim()) handleSelect(input);
    } else if (e.key === "Escape") {
      setOpen(false);
      setInput("");
    }
  };

  return (
    <div className="flex flex-wrap gap-1.5 items-center">
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={tags.map((t) => t!.id)} strategy={horizontalListSortingStrategy}>
          {tags.map((tag) => tag && (
            <SortableTagPill
              key={tag.id}
              tag={tag}
              onDelete={(id) => deleteTag.mutate(id)}
            />
          ))}
        </SortableContext>
      </DndContext>

      <div className="relative" ref={popoverRef}>
        <button
          onClick={() => setOpen((v) => !v)}
          className="inline-flex items-center gap-0.5 rounded-full border border-dashed border-border px-2 py-0.5 text-label text-muted-foreground hover:border-primary/50 hover:text-primary transition-colors"
        >
          <Plus className="h-3 w-3" />
          태그 추가
        </button>

        {open && (
          <div className="absolute top-full left-0 mt-1.5 z-50 bg-card border border-border rounded-lg shadow-xl w-52">
            <div className="px-2 pt-2 pb-1 border-b border-border/50">
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="태그 검색 또는 입력..."
                className="w-full bg-transparent text-label outline-none placeholder:text-muted-foreground/50 py-0.5"
              />
            </div>

            <div className="py-1 max-h-48 overflow-y-auto">
              {suggestions.length > 0 ? (
                suggestions.map((t) => (
                  <button
                    key={t}
                    onMouseDown={(e) => { e.preventDefault(); handleSelect(t); }}
                    className="w-full flex items-center px-3 py-1.5 hover:bg-secondary/60 transition-colors"
                  >
                    <span
                      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-label font-medium border"
                      style={tagStyle(t)}
                    >
                      {t}
                    </span>
                  </button>
                ))
              ) : input.trim() ? (
                <button
                  onMouseDown={(e) => { e.preventDefault(); handleSelect(input); }}
                  className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-secondary/60 transition-colors"
                >
                  <Plus className="h-3 w-3 text-muted-foreground shrink-0" />
                  <span className="text-label text-muted-foreground">생성:</span>
                  <span
                    className="inline-flex items-center rounded-full px-2.5 py-0.5 text-label font-medium border"
                    style={tagStyle(input.trim())}
                  >
                    {input.trim()}
                  </span>
                </button>
              ) : (
                <p className="px-3 py-2 text-label text-muted-foreground/60">
                  아직 만든 태그가 없습니다
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
