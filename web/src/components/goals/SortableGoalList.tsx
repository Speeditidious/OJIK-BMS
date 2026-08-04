"use client";

import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  useSortable,
  type SortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { GoalRecord } from "@/hooks/use-goals";
import { useReorderGoals } from "@/hooks/use-goals";

interface SortableGoalListProps {
  /** Goals in the order the server returned them. */
  goals: GoalRecord[];
  strategy: SortingStrategy;
  /** True when the viewer may not reorder — a visitor, or a filtered view. */
  disabled: boolean;
  /**
   * Tooltip for a dimmed, non-functional grip. Provide it when reordering is
   * temporarily blocked and the user deserves an explanation; omit it to hide
   * the grip entirely (visitors, who can never reorder).
   */
  disabledReason?: string;
  className?: string;
  renderItem: (goal: GoalRecord, dragHandle: ReactNode) => ReactNode;
}

/**
 * Drag-to-reorder wrapper shared by the dashboard profile card's goal grid
 * and the goals tab's active list. Both read the same `["goals"]` query
 * family, so an order set in one is visible in the other after the mutation
 * settles.
 */
export function SortableGoalList({
  goals,
  strategy,
  disabled,
  disabledReason,
  className,
  renderItem,
}: SortableGoalListProps) {
  const reorder = useReorderGoals();
  // Optimistic order held only while the mutation is in flight; cleared once
  // the refetched server order is authoritative.
  const [localGoals, setLocalGoals] = useState<GoalRecord[] | null>(null);
  const displayed = localGoals ?? goals;

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const current = localGoals ?? goals;
    const oldIndex = current.findIndex((goal) => goal.goal_id === active.id);
    const newIndex = current.findIndex((goal) => goal.goal_id === over.id);
    if (oldIndex === -1 || newIndex === -1) return;

    const reordered = arrayMove(current, oldIndex, newIndex);
    setLocalGoals(reordered);
    reorder.mutate(
      reordered.map((goal) => goal.goal_id),
      { onSuccess: () => setLocalGoals(null) },
    );
  }

  return (
    <TooltipProvider delayDuration={150}>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={displayed.map((goal) => goal.goal_id)} strategy={strategy}>
          <div className={className}>
            {displayed.map((goal) => (
              <SortableGoalItem
                key={goal.goal_id}
                goal={goal}
                disabled={disabled}
                disabledReason={disabledReason}
                renderItem={renderItem}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </TooltipProvider>
  );
}

function SortableGoalItem({
  goal,
  disabled,
  disabledReason,
  renderItem,
}: {
  goal: GoalRecord;
  disabled: boolean;
  disabledReason?: string;
  renderItem: (goal: GoalRecord, dragHandle: ReactNode) => ReactNode;
}) {
  const { t } = useTranslation();
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: goal.goal_id,
    disabled,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  // Drag is grip-only: the card body carries a song link and a delete button,
  // and the grip is where the explanatory tooltip lives.
  let dragHandle: ReactNode = null;
  if (!disabled) {
    dragHandle = (
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            {...attributes}
            {...listeners}
            className="shrink-0 cursor-grab opacity-40 transition-opacity hover:opacity-80 active:cursor-grabbing"
            aria-label={t("goals.card.reorderTitle")}
          >
            <GripVertical className="h-4 w-4 text-muted-foreground" />
          </button>
        </TooltipTrigger>
        <TooltipContent className="text-label">{t("goals.card.reorderTitle")}</TooltipContent>
      </Tooltip>
    );
  } else if (disabledReason) {
    // A `disabled` button emits no pointer events, so the tooltip would never
    // open — render a plain span instead.
    dragHandle = (
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="shrink-0 cursor-not-allowed opacity-25">
            <GripVertical className="h-4 w-4 text-muted-foreground" />
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs text-label">{disabledReason}</TooltipContent>
      </Tooltip>
    );
  }

  return (
    <div ref={setNodeRef} style={style}>
      {renderItem(goal, dragHandle)}
    </div>
  );
}
