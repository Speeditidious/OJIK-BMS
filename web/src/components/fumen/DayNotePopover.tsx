"use client";

import { useState } from "react";
import { StickyNote, Pencil, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { MarkdownContent } from "@/components/common/MarkdownContent";
import { MarkdownEditor } from "@/components/common/MarkdownEditor";
import { useDayNote, useUpsertDayNote, useDeleteDayNote } from "@/hooks/use-day-notes";
import { timeAgo } from "@/lib/time";

interface DayNotePopoverProps {
  userId: string;
  date: string;
  isOwner: boolean;
  /** When true the trigger is a plain icon (calendar cell). Stop-propagation is applied. */
  cellTrigger?: boolean;
  /** Pre-known note presence for initial icon color (before the note is lazily fetched). */
  hasNote?: boolean;
}

export function DayNotePopover({ userId, date, isOwner, cellTrigger = false, hasNote }: DayNotePopoverProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);

  const { data: note, isLoading } = useDayNote(open ? userId : null, open ? date : null);
  const upsert = useUpsertDayNote(userId);
  const remove = useDeleteDayNote(userId);

  // Persist note state across open/close cycles so icon color doesn't reset.
  // React "storing information from previous renders" pattern (avoids ref during render).
  const [lastKnownNote, setLastKnownNote] = useState<typeof note>(undefined);
  if (note !== undefined && note !== lastKnownNote) {
    setLastKnownNote(note);
  }
  const noteExists = lastKnownNote !== undefined
    ? lastKnownNote !== null
    : (hasNote ?? false);

  // When owner opens popover and there's no note, enter editing mode automatically
  const showEditor = editing || (isOwner && !note && !isLoading && open);

  function handleTriggerClick(e: React.MouseEvent) {
    if (cellTrigger) e.stopPropagation();
    setOpen((prev) => !prev);
  }

  async function handleSave(content: string) {
    await upsert.mutateAsync({ date, content });
    setEditing(false);
  }

  async function handleDelete() {
    await remove.mutateAsync(date);
    // note is now gone → editor will auto-open via showEditor logic
    setEditing(false);
  }

  const trigger = cellTrigger ? (
    <button
      type="button"
      onClick={handleTriggerClick}
      aria-label={t("dashboard.calendar.hasNote")}
      className="text-primary/70 hover:text-primary transition-colors"
    >
      <StickyNote className="h-3.5 w-3.5" />
    </button>
  ) : (
    <Button
      variant="ghost"
      size="icon"
      className={`h-8 w-8 shrink-0 hover:text-foreground ${noteExists ? "text-primary" : "text-muted-foreground"}`}
      onClick={handleTriggerClick}
      aria-label={t("dashboard.dayDetail.note.title")}
    >
      <StickyNote className="h-6 w-6" />
    </Button>
  );

  return (
    <Popover open={open} onOpenChange={(v) => { setOpen(v); if (!v) setEditing(false); }}>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent className="w-96 p-0 overflow-hidden" align="end">
        {/* Header */}
        <div className="border-b bg-muted/30">
          <div className="flex items-center justify-between px-3 pt-2 pb-1.5">
            <div className="flex items-center gap-1.5">
              <StickyNote className="h-3.5 w-3.5 text-primary shrink-0" />
              <span className="text-label font-medium">{t("dashboard.dayDetail.note.title")}</span>
            </div>
            <div className="flex items-center gap-1">
              {isOwner && !editing && note && (
                <>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 text-muted-foreground hover:text-foreground"
                    onClick={() => setEditing(true)}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 text-muted-foreground hover:text-destructive"
                    onClick={handleDelete}
                    disabled={remove.isPending}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </>
              )}
            </div>
          </div>
          {note && (
            <div className="px-3 pb-2 text-xs text-muted-foreground/60">
              {t("issues.list.created")} {timeAgo(note.created_at, t)}
              {note.created_at !== note.updated_at && (
                <> · {t("issues.list.updated")} {timeAgo(note.updated_at, t)}</>
              )}
            </div>
          )}
        </div>

        {/* Body */}
        <div className="max-h-[28rem] overflow-y-auto">
          {isLoading ? (
            <p className="p-4 text-label text-muted-foreground">{t("common.status.loading")}</p>
          ) : showEditor ? (
            <div className="p-4">
              <MarkdownEditor
                initialBody={note?.content ?? ""}
                onSave={handleSave}
                onCancel={() => { setEditing(false); if (!note) setOpen(false); }}
                isSaving={upsert.isPending}
                placeholder={t("dashboard.dayDetail.note.placeholder")}
                maxLength={2000}
              />
            </div>
          ) : note ? (
            <div className="p-4">
              <MarkdownContent>{note.content}</MarkdownContent>
            </div>
          ) : (
            <p className="p-4 text-label text-muted-foreground italic">{t("dashboard.dayDetail.note.empty")}</p>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
