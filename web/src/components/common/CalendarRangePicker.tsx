"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { X } from "lucide-react";
import { CalendarPopover } from "@/components/common/CalendarPopover";
import { previewRange } from "@/lib/calendar-grid-core";

export interface CalendarRangeValue {
  from: string | null;
  to: string | null;
}

interface CalendarRangePickerProps {
  value: CalendarRangeValue;
  onChange: (next: CalendarRangeValue) => void;
  /** Trigger button text shown when no range is selected. */
  label: string;
  className?: string;
}

/**
 * Inclusive `from`..`to` date range picker built on `CalendarPopover`.
 *
 * The first click starts a range and keeps the popover open; while only that
 * bound is set, hovering a day previews the range that click would commit.
 * The second click closes the popover, swapping the bounds when the second
 * day is earlier.
 */
export function CalendarRangePicker({ value, onChange, label, className }: CalendarRangePickerProps) {
  const { t } = useTranslation();
  const [hoverDate, setHoverDate] = useState<string | null>(null);
  const hasRange = !!value.from || !!value.to;
  const preview = previewRange(value.from, value.to, hoverDate);

  function handleDayClick(dateStr: string) {
    setHoverDate(null);
    // No open range yet (nothing selected, or both bounds already set) -> start over.
    if (!value.from || value.to) {
      onChange({ from: dateStr, to: null });
      return;
    }
    if (dateStr < value.from) onChange({ from: dateStr, to: value.from });
    else onChange({ from: value.from, to: dateStr });
  }

  return (
    <CalendarPopover
      className={className}
      label={hasRange ? `${value.from ?? ""} ~ ${value.to ?? ""}` : label}
      highlighted={hasRange}
      trailing={
        hasRange ? (
          <button
            type="button"
            aria-label={t("goals.filter.clearDates")}
            onClick={() => onChange({ from: null, to: null })}
            className="rounded p-1 text-muted-foreground transition-colors hover:bg-secondary/60 hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        ) : undefined
      }
      getDayState={(dateStr) => ({
        selected: dateStr === value.from || dateStr === value.to,
        inRange:
          (!!value.from && !!value.to && dateStr > value.from && dateStr < value.to) ||
          (!!preview && dateStr > preview.from && dateStr < preview.to),
        previewEnd: !!preview && dateStr === hoverDate && dateStr !== value.from,
      })}
      onDayClick={handleDayClick}
      onDayHover={setHoverDate}
      // Keep the popover open while only the start bound is set.
      shouldCloseOnDayClick={() => !!value.from && !value.to}
      footerSlot={
        <div className="flex items-center justify-between pt-1 text-caption text-muted-foreground tabular-nums">
          <span>{t("common.calendar.start")}: {value.from ?? "-"}</span>
          <span>{t("common.calendar.end")}: {value.to ?? "-"}</span>
        </div>
      }
    />
  );
}
