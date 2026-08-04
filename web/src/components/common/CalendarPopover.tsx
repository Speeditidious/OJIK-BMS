"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import {
  buildMonthCells,
  getMonthRange,
  isMonthAfter,
  pad2,
  shiftMonth,
  toDateString,
} from "@/lib/calendar-grid-core";
import { cn } from "@/lib/utils";

/** How a single day cell should be painted. */
export interface CalendarDayState {
  /** A range endpoint, or the single selected day. */
  selected?: boolean;
  /** Strictly between two range endpoints, or inside a hover preview. */
  inRange?: boolean;
  /** The hovered end of a range that has not been committed yet. */
  previewEnd?: boolean;
  /** Small marker under the day number (e.g. "there are records here"). */
  dot?: boolean;
}

interface CalendarPopoverProps {
  /** Trigger button text. */
  label: string;
  /** Renders the trigger in its "a value is selected" style. */
  highlighted?: boolean;
  /** Rendered next to the trigger, outside the popover (e.g. a clear button). */
  trailing?: React.ReactNode;
  /** Rendered inside the popover, above the month grid. */
  headerSlot?: React.ReactNode;
  /** Rendered inside the popover, below the month grid. */
  footerSlot?: React.ReactNode;
  /** Fires with the visible month's inclusive range on open and on every nav. */
  onVisibleMonthChange?: (from: string, to: string) => void;
  getDayState: (dateStr: string) => CalendarDayState;
  onDayClick: (dateStr: string) => void;
  /** Fires with the hovered/focused day, and with null when the pointer leaves. */
  onDayHover?: (dateStr: string | null) => void;
  /** Whether the popover closes after a day click. Defaults to always closing. */
  shouldCloseOnDayClick?: (dateStr: string) => boolean;
  className?: string;
}

// 2024-01-07 is a Sunday; use it as a stable reference for Sun..Sat. Same
// approach as ActivityCalendar's weekday header.
function buildWeekdayLabels(locale: string): string[] {
  const formatter = new Intl.DateTimeFormat(locale, { weekday: "short", timeZone: "UTC" });
  return Array.from({ length: 7 }, (_, i) => formatter.format(new Date(Date.UTC(2024, 0, 7 + i))));
}

/**
 * Shared calendar popup: trigger button, click-outside dismissal, month
 * navigation with future months disabled, a localized weekday header, and a
 * six-week day grid whose per-day appearance the caller controls.
 *
 * Selection semantics live in the caller — `SnapshotDatePicker` picks a
 * single day, `CalendarRangePicker` picks a from..to range.
 */
export function CalendarPopover({
  label,
  highlighted = false,
  trailing,
  headerSlot,
  footerSlot,
  onVisibleMonthChange,
  getDayState,
  onDayClick,
  onDayHover,
  shouldCloseOnDayClick,
  className,
}: CalendarPopoverProps) {
  const { t, i18n } = useTranslation();
  const today = useMemo(() => new Date(), []);
  const todayStr = toDateString(today.getFullYear(), today.getMonth() + 1, today.getDate());

  const [isOpen, setIsOpen] = useState(false);
  const [view, setView] = useState({ year: today.getFullYear(), month: today.getMonth() + 1 });
  const containerRef = useRef<HTMLDivElement>(null);

  const weekdayLabels = useMemo(() => buildWeekdayLabels(i18n.language), [i18n.language]);
  const cells = useMemo(() => buildMonthCells(view.year, view.month), [view]);

  function notifyMonth(year: number, month: number) {
    if (!onVisibleMonthChange) return;
    const { from, to } = getMonthRange(year, month);
    onVisibleMonthChange(from, to);
  }

  function handleToggle() {
    const next = !isOpen;
    setIsOpen(next);
    if (next) notifyMonth(view.year, view.month);
  }

  function navigate(delta: number) {
    const next = shiftMonth(view.year, view.month, delta);
    setView(next);
    notifyMonth(next.year, next.month);
  }

  useEffect(() => {
    if (!isOpen) {
      // A closed popover has no hovered day; leaving it set would keep a
      // stale preview painted the next time it opens.
      onDayHover?.(null);
      return;
    }
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  // onDayHover is a stable setter in practice; re-subscribing on identity
  // changes would tear down the listener on every parent render.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const nextMonth = shiftMonth(view.year, view.month, 1);
  const isNextMonthFuture = isMonthAfter(nextMonth.year, nextMonth.month, todayStr);

  return (
    <div ref={containerRef} className={cn("relative inline-block", className)}>
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={handleToggle}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md border px-3 py-2 text-label font-medium transition-colors",
            highlighted
              ? "border-primary/60 bg-primary/15 text-primary hover:bg-primary/20"
              : "border-border bg-secondary text-foreground hover:border-primary/40 hover:bg-secondary/80",
          )}
        >
          <CalendarDays className="h-3.5 w-3.5 shrink-0" />
          <span className="tabular-nums">{label}</span>
        </button>
        {trailing}
      </div>

      {isOpen && (
        <div className="absolute left-0 top-full z-50 mt-1 w-[280px] space-y-2 rounded-lg border border-border bg-card p-3 shadow-lg">
          {headerSlot}

          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => navigate(-1)}
              aria-label={t("common.calendar.prevMonth")}
              className="rounded p-1 text-muted-foreground transition-colors hover:bg-secondary/50 hover:text-foreground"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-label font-medium text-foreground tabular-nums">
              {t("format.axis.monthYear", { year: view.year, month: pad2(view.month) })}
            </span>
            <button
              type="button"
              onClick={() => navigate(1)}
              disabled={isNextMonthFuture}
              aria-label={t("common.calendar.nextMonth")}
              className={cn(
                "rounded p-1 transition-colors",
                isNextMonthFuture
                  ? "cursor-not-allowed text-muted-foreground opacity-30"
                  : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground",
              )}
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="grid grid-cols-7 text-center">
            {weekdayLabels.map((weekdayLabel) => (
              <div key={weekdayLabel} className="py-1 text-caption font-medium text-muted-foreground">
                {weekdayLabel}
              </div>
            ))}
          </div>

          <div
            className="grid grid-cols-7 gap-y-0.5"
            onMouseLeave={() => onDayHover?.(null)}
          >
            {cells.map(({ dateStr, day, currentMonth }) => {
              const isFuture = dateStr > todayStr;
              const isToday = dateStr === todayStr;
              const { selected, inRange, previewEnd, dot } = getDayState(dateStr);
              return (
                <button
                  key={dateStr}
                  type="button"
                  disabled={isFuture}
                  onMouseEnter={() => !isFuture && onDayHover?.(dateStr)}
                  onFocus={() => !isFuture && onDayHover?.(dateStr)}
                  onClick={() => {
                    onDayClick(dateStr);
                    if (!shouldCloseOnDayClick || shouldCloseOnDayClick(dateStr)) {
                      setIsOpen(false);
                    }
                  }}
                  className={cn(
                    "relative flex flex-col items-center justify-center rounded py-1 text-label tabular-nums transition-colors",
                    !currentMonth && "opacity-25",
                    isFuture && "cursor-not-allowed opacity-40",
                    selected && "bg-primary/25 font-semibold text-primary",
                    !selected && previewEnd && "border border-primary/60 font-medium text-primary",
                    !selected && !previewEnd && inRange && "bg-primary/10 text-primary",
                    !selected && !previewEnd && !inRange && isToday && "font-medium text-primary",
                    !selected && !previewEnd && !inRange && !isFuture && currentMonth &&
                      "hover:bg-secondary/50",
                  )}
                >
                  <span>{day}</span>
                  {dot && (
                    <span
                      className={cn(
                        "absolute bottom-0.5 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full",
                        selected ? "bg-primary/60" : "bg-primary/40",
                      )}
                    />
                  )}
                </button>
              );
            })}
          </div>

          {footerSlot}
        </div>
      )}
    </div>
  );
}
