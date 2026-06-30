"use client";

import { Pencil } from "lucide-react";
import { MarkdownContent } from "@/components/common/MarkdownContent";
import { DayNotePopover } from "@/components/fumen/DayNotePopover";
import type { DayNote } from "@/hooks/use-day-notes";

interface DayStatHeaderNoteProps {
  userId: string;
  date: string;
  isOwner: boolean;
  note: DayNote | null | undefined;
}

/**
 * Day-sheet header memo. Centered in the right column that spans the full card
 * height. The memo content is rendered inline so it is captured in the exported
 * image; all edit affordances are export-excluded.
 *
 * - No memo (owner): a centered "메모" button opens the editor.
 * - Has memo (owner): the content itself is the click target — hovering hints
 *   it is editable; clicking opens the same memo popover. No separate button.
 * - Has memo (non-owner): content only, not interactive.
 */
export function DayStatHeaderNote({ userId, date, isOwner, note }: DayStatHeaderNoteProps) {
  const noteTitle = note?.title?.trim() ?? "";
  const noteBody = note?.content?.trim() ?? "";
  // A note counts as present if it has a title or a body (title-only is valid).
  const hasContent = !!note && (noteTitle.length > 0 || noteBody.length > 0);

  // Non-owner with no memo → empty region.
  if (!hasContent && !isOwner) return null;

  const content = hasContent ? (
    <div className="min-w-0 max-w-full text-center">
      {noteTitle && (
        <p className={`text-[26px] font-bold text-foreground${noteBody ? " mb-1" : ""}`}>{noteTitle}</p>
      )}
      {noteBody && <MarkdownContent className="text-base">{noteBody}</MarkdownContent>}
    </div>
  ) : null;

  // Non-owner: display content only, no editing.
  if (!isOwner) return content;

  // Owner + memo exists → content is the trigger; hover hints it is editable.
  if (hasContent) {
    return (
      <DayNotePopover
        userId={userId}
        date={date}
        isOwner
        hasNote
        customTrigger={
          <div
            role="button"
            tabIndex={0}
            className="group relative flex h-full w-full cursor-pointer items-center justify-center rounded-xl px-4 py-3 transition-colors hover:bg-muted/40"
          >
            {content}
            <span
              data-export-exclude
              className="pointer-events-none absolute right-2 top-2 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
            >
              <Pencil className="h-4 w-4" />
            </span>
          </div>
        }
      />
    );
  }

  // Owner + no memo → centered "메모" button (excluded from the export).
  return (
    <div data-export-exclude>
      <DayNotePopover userId={userId} date={date} isOwner hasNote={false} />
    </div>
  );
}
