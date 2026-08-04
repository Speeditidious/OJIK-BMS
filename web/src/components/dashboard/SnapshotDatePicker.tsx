"use client";

import { useTranslation } from "react-i18next";
import { CalendarPopover } from "@/components/common/CalendarPopover";

interface SnapshotDatePickerProps {
  selectedDate: string | null;
  onSelect: (date: string | null) => void;
  playRecordDates: Set<string>;
  onMonthChange?: (from: string, to: string) => void;
}

/**
 * Single-day "view past records" picker, built on the shared
 * `CalendarPopover`. Days that have play records get a dot, and an inline
 * action resets the view back to the user's current records.
 */
export function SnapshotDatePicker({
  selectedDate,
  onSelect,
  playRecordDates,
  onMonthChange,
}: SnapshotDatePickerProps) {
  const { t } = useTranslation();

  return (
    <CalendarPopover
      label={selectedDate ? selectedDate.replace(/-/g, ".") : t("dashboard.tableClear.viewSnapshot")}
      highlighted={!!selectedDate}
      onVisibleMonthChange={onMonthChange}
      getDayState={(dateStr) => ({
        selected: dateStr === selectedDate,
        dot: playRecordDates.has(dateStr),
      })}
      onDayClick={(dateStr) => onSelect(dateStr)}
      headerSlot={
        selectedDate ? (
          <button
            type="button"
            onClick={() => onSelect(null)}
            className="w-full rounded px-1 py-0.5 text-left text-label text-primary/80 transition-colors hover:text-primary"
          >
            {t("dashboard.tableClear.viewCurrent")}
          </button>
        ) : undefined
      }
    />
  );
}
