"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
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
import { ChevronDown, ChevronUp, GripVertical, ImageDown, RotateCcw, Settings } from "lucide-react";
import type { DayStatSheetPrefs, RatingSubKey, UpdateSectionKey } from "@/hooks/use-preferences";
import { DEFAULT_DAY_SHEET_PREFS } from "@/hooks/use-preferences";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface TableOption {
  slug: string;
  display_name: string;
  has_bmsforce: boolean;
}

interface DayStatSheetToolbarProps {
  allTables: TableOption[];
  prefs: DayStatSheetPrefs;
  onPrefsChange: (p: Partial<DayStatSheetPrefs>) => void;
  onSave: () => void;
  isSaving: boolean;
  saveError?: string | null;
  availableDans: string[];
}

// ── Sortable horizontal pill ───────────────────────────────────────────────────
// Grip handles drag; clicking the label area toggles ON/OFF (when onToggle provided).

function SortableHorizontalPill({
  id,
  label,
  checked,
  onToggle,
  disabled,
}: {
  id: string;
  label: string;
  checked?: boolean;
  onToggle?: () => void;
  disabled?: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id });

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 }}
      className={cn(
        "inline-flex shrink-0 items-center rounded-full border text-label select-none overflow-hidden",
        checked === false
          ? "border-border/30 bg-background text-muted-foreground/40"
          : checked === true
          ? "border-primary/60 bg-primary/10 text-primary font-medium"
          : "border-border/50 bg-background text-muted-foreground",
        isDragging && "ring-1 ring-primary/40",
        disabled && "pointer-events-none opacity-40",
      )}
    >
      {/* Drag handle — drag events only */}
      <button
        type="button"
        {...attributes}
        {...listeners}
        className="pl-2.5 py-1 shrink-0 cursor-grab text-muted-foreground/60 transition-colors hover:text-foreground active:cursor-grabbing"
        aria-label={`Reorder ${label}`}
      >
        <GripVertical className="h-3.5 w-3.5" />
      </button>
      {/* Label area — click to toggle */}
      <span
        onClick={onToggle}
        className={cn("pr-2.5 pl-1.5 py-1", onToggle && "cursor-pointer")}
      >
        {label}
      </span>
    </div>
  );
}

// ── Category header with SquareCheck icon toggle ───────────────────────────────

function CategoryHeader({
  label,
  sectionEnabled,
  onToggle,
}: {
  label: string;
  sectionEnabled: boolean;
  onToggle: () => void;
}) {
  return (
    <label className="flex cursor-pointer select-none items-center gap-1.5">
      <p className="text-label font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <input
        type="checkbox"
        checked={sectionEnabled}
        onChange={onToggle}
        className="accent-primary"
      />
    </label>
  );
}

// ── Toolbar ────────────────────────────────────────────────────────────────────

export function DayStatSheetToolbar({
  allTables,
  prefs,
  onPrefsChange,
  onSave,
  isSaving,
  saveError,
  availableDans,
}: DayStatSheetToolbarProps) {
  const { t } = useTranslation();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  // ── Table ──────────────────────────────────────────────────────────────────

  function toggleTable(slug: string) {
    const current = prefs.day_sheet_tables ?? allTables.filter((t) => t.has_bmsforce).map((t) => t.slug);
    const next = current.includes(slug)
      ? current.filter((s) => s !== slug)
      : [...current, slug];
    onPrefsChange({ day_sheet_tables: next.length === 0 ? null : next });
  }

  function handleTableDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const current = prefs.day_sheet_tables ?? allTables.filter((t) => t.has_bmsforce).map((t) => t.slug);
    const oldIndex = current.indexOf(active.id as string);
    const newIndex = current.indexOf(over.id as string);
    if (oldIndex === -1 || newIndex === -1) return;
    onPrefsChange({
      day_sheet_tables: arrayMove(current, oldIndex, newIndex),
      // Freeze current dan order so table reordering doesn't disturb it
      day_sheet_dan_order: prefs.day_sheet_dan_order ?? orderedDans,
    });
  }

  const selectedSlugs = prefs.day_sheet_tables ?? allTables.filter((t) => t.has_bmsforce).map((t) => t.slug);

  // ── Dan ────────────────────────────────────────────────────────────────────

  function handleDanDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const current = prefs.day_sheet_dan_order ?? availableDans;
    const oldIndex = current.indexOf(active.id as string);
    const newIndex = current.indexOf(over.id as string);
    if (oldIndex === -1 || newIndex === -1) return;
    onPrefsChange({ day_sheet_dan_order: arrayMove(current, oldIndex, newIndex) });
  }

  const orderedDans = (() => {
    const preferredOrder = prefs.day_sheet_dan_order;
    if (!preferredOrder) return [...availableDans];
    const knownInOrder = preferredOrder.filter((d) => availableDans.includes(d));
    const rest = availableDans.filter((d) => !preferredOrder.includes(d));
    return [...knownInOrder, ...rest];
  })();

  // ── Rating sub-sections ────────────────────────────────────────────────────

  function handleRatingDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const order = [...prefs.day_sheet_rating_order];
    const oldIndex = order.indexOf(active.id as RatingSubKey);
    const newIndex = order.indexOf(over.id as RatingSubKey);
    if (oldIndex === -1 || newIndex === -1) return;
    onPrefsChange({ day_sheet_rating_order: arrayMove(order, oldIndex, newIndex) });
  }

  function ratingSubLabel(key: RatingSubKey): string {
    return key === "rating_info"
      ? t("dashboard.daySheet.showRatingInfo")
      : t("dashboard.daySheet.showExpInfo");
  }

  function ratingSubChecked(key: RatingSubKey): boolean {
    return key === "rating_info" ? prefs.day_sheet_show_rating_info : prefs.day_sheet_show_exp_info;
  }

  function toggleRatingSub(key: RatingSubKey) {
    if (key === "rating_info") {
      onPrefsChange({ day_sheet_show_rating_info: !prefs.day_sheet_show_rating_info });
    } else {
      onPrefsChange({ day_sheet_show_exp_info: !prefs.day_sheet_show_exp_info });
    }
  }

  // ── Record sections ────────────────────────────────────────────────────────

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const order = [...prefs.day_sheet_update_order];
    const oldIndex = order.indexOf(active.id as UpdateSectionKey);
    const newIndex = order.indexOf(over.id as UpdateSectionKey);
    if (oldIndex === -1 || newIndex === -1) return;
    onPrefsChange({ day_sheet_update_order: arrayMove(order, oldIndex, newIndex) });
  }

  function toggleVisible(key: UpdateSectionKey) {
    onPrefsChange({
      day_sheet_update_visible: {
        ...prefs.day_sheet_update_visible,
        [key]: !prefs.day_sheet_update_visible[key],
      },
    });
  }

  function sectionLabel(key: UpdateSectionKey): string {
    switch (key) {
      case "clear": return t("dashboard.daySheet.sectionClear");
      case "score": return t("dashboard.daySheet.sectionScore");
      case "bp":    return t("dashboard.daySheet.sectionBp");
      case "combo": return t("dashboard.daySheet.sectionCombo");
    }
  }

  // ── Derived ────────────────────────────────────────────────────────────────

  const blockLabelCls = "text-label font-semibold uppercase tracking-wide text-muted-foreground";
  const ratingOff = !prefs.day_sheet_show_rating_section;
  const recordOff = !prefs.day_sheet_show_record_section;

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border/40 bg-muted/20 p-4">
      {/* Action row */}
      <div className="flex items-center gap-2">
        <Button
          variant="default"
          size="lg"
          className="flex-1 gap-2 text-base font-semibold"
          onClick={onSave}
          disabled={isSaving}
        >
          <ImageDown className="h-5 w-5 shrink-0" />
          {isSaving ? t("dashboard.scoreUpdates.imageSaving") : t("dashboard.scoreUpdates.saveImage")}
        </Button>
        <Button
          variant="outline"
          size="lg"
          className="gap-1.5 shrink-0"
          onClick={() => setIsSettingsOpen((v) => !v)}
        >
          <Settings className="h-4 w-4" />
          {t("dashboard.daySheet.openSettings")}
          {isSettingsOpen ? (
            <ChevronUp className="h-3.5 w-3.5" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5" />
          )}
        </Button>
      </div>

      {saveError && <p className="text-label text-destructive">{saveError}</p>}

      {/* Collapsible settings panel */}
      {isSettingsOpen && (
        <div className="relative flex flex-col gap-4 border-t border-border/40 pt-4">

          <Button
            variant="ghost"
            size="sm"
            className="absolute right-0 top-4 h-6 gap-1 text-label text-muted-foreground hover:text-foreground"
            onClick={() => onPrefsChange(DEFAULT_DAY_SHEET_PREFS)}
          >
            <RotateCcw className="h-3 w-3" />
            {t("dashboard.daySheet.resetSettings")}
          </Button>

          {/* ── 난이도표 ──────────────────────────────────────────────── */}
          {allTables.length > 0 && (
            <div className="space-y-2">
              <p className={blockLabelCls}>{t("dashboard.daySheet.selectTables")}</p>
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleTableDragEnd}>
                <SortableContext items={selectedSlugs} strategy={horizontalListSortingStrategy}>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedSlugs.map((slug) => {
                      const table = allTables.find((t) => t.slug === slug);
                      if (!table) return null;
                      return (
                        <SortableHorizontalPill
                          key={slug}
                          id={slug}
                          label={table.display_name}
                          checked={true}
                          onToggle={() => toggleTable(slug)}
                        />
                      );
                    })}
                    {allTables
                      .filter((t) => !selectedSlugs.includes(t.slug))
                      .map((table) => (
                        <button
                          key={table.slug}
                          type="button"
                          onClick={() => toggleTable(table.slug)}
                          className="inline-flex items-center rounded-full border border-border/30 px-2.5 py-1 text-label text-muted-foreground/40 transition-colors hover:border-primary/40 hover:text-muted-foreground"
                        >
                          {table.display_name}
                        </button>
                      ))}
                  </div>
                </SortableContext>
              </DndContext>
            </div>
          )}

          {/* ── 단위 ──────────────────────────────────────────────────── */}
          {orderedDans.length > 0 && (
            <div className="space-y-2">
              <p className={blockLabelCls}>{t("dashboard.daySheet.danLabel")}</p>
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDanDragEnd}>
                <SortableContext items={orderedDans} strategy={horizontalListSortingStrategy}>
                  <div className="flex flex-wrap gap-1.5">
                    {orderedDans.map((dan) => (
                      <SortableHorizontalPill key={dan} id={dan} label={dan} />
                    ))}
                  </div>
                </SortableContext>
              </DndContext>
            </div>
          )}

          {/* ── 레이팅 변동 ───────────────────────────────────────────── */}
          <div className="space-y-2">
            <CategoryHeader
              label={t("dashboard.daySheet.ratingOptions")}
              sectionEnabled={prefs.day_sheet_show_rating_section}
              onToggle={() =>
                onPrefsChange({ day_sheet_show_rating_section: !prefs.day_sheet_show_rating_section })
              }
            />
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleRatingDragEnd}>
              <SortableContext items={prefs.day_sheet_rating_order} strategy={horizontalListSortingStrategy}>
                <div className={cn("flex flex-wrap gap-1.5", ratingOff && "pointer-events-none opacity-40")}>
                  {prefs.day_sheet_rating_order.map((key) => (
                    <SortableHorizontalPill
                      key={key}
                      id={key}
                      label={ratingSubLabel(key)}
                      checked={ratingSubChecked(key)}
                      onToggle={() => toggleRatingSub(key)}
                      disabled={ratingOff}
                    />
                  ))}
                </div>
              </SortableContext>
            </DndContext>
          </div>

          {/* ── 기록 상세 ─────────────────────────────────────────────── */}
          <div className="space-y-2">
            <CategoryHeader
              label={t("dashboard.daySheet.recordOptions")}
              sectionEnabled={prefs.day_sheet_show_record_section}
              onToggle={() =>
                onPrefsChange({ day_sheet_show_record_section: !prefs.day_sheet_show_record_section })
              }
            />
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext items={prefs.day_sheet_update_order} strategy={horizontalListSortingStrategy}>
                <div className={cn("flex flex-wrap gap-1.5", recordOff && "pointer-events-none opacity-40")}>
                  {prefs.day_sheet_update_order.map((key) => (
                    <SortableHorizontalPill
                      key={key}
                      id={key}
                      label={sectionLabel(key)}
                      checked={!!prefs.day_sheet_update_visible[key]}
                      onToggle={() => toggleVisible(key)}
                      disabled={recordOff}
                    />
                  ))}
                </div>
              </SortableContext>
            </DndContext>

            {/* Memo lives in the header, so it stays toggleable even when the record section is off. */}
            <label className="flex w-fit cursor-pointer select-none items-center gap-1.5 pt-1">
              <p className="text-label font-semibold uppercase tracking-wide text-muted-foreground">{t("dashboard.daySheet.showNote")}</p>
              <input
                type="checkbox"
                checked={prefs.day_sheet_show_note}
                onChange={() => onPrefsChange({ day_sheet_show_note: !prefs.day_sheet_show_note })}
                className="accent-primary"
              />
            </label>
          </div>

        </div>
      )}
    </div>
  );
}
