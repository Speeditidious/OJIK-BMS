"use client";

import React, { useState, useRef, useEffect } from "react";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

interface SnapshotDatePickerProps {
  selectedDate: string | null;
  onSelect: (date: string | null) => void;
  playRecordDates: Set<string>;
  onMonthChange?: (from: string, to: string) => void;
}

const DAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function toDateString(year: number, month: number, day: number): string {
  return `${year}-${pad2(month)}-${pad2(day)}`;
}

function getMonthRange(year: number, month: number): { from: string; to: string } {
  const lastDay = new Date(year, month, 0).getDate();
  return {
    from: toDateString(year, month, 1),
    to: toDateString(year, month, lastDay),
  };
}

export function SnapshotDatePicker({
  selectedDate,
  onSelect,
  playRecordDates,
  onMonthChange,
}: SnapshotDatePickerProps) {
  const { t } = useTranslation();
  const today = new Date();
  const todayStr = toDateString(today.getFullYear(), today.getMonth() + 1, today.getDate());

  const [isOpen, setIsOpen] = useState(false);
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth() + 1); // 1-based

  const containerRef = useRef<HTMLDivElement>(null);

  // Notify parent when month changes
  const notifyMonthChange = (year: number, month: number) => {
    if (!onMonthChange) return;
    const { from, to } = getMonthRange(year, month);
    onMonthChange(from, to);
  };

  // When calendar opens, notify parent of current month
  const handleOpen = () => {
    setIsOpen(true);
    notifyMonthChange(viewYear, viewMonth);
  };

  const handlePrevMonth = () => {
    let y = viewYear;
    let m = viewMonth - 1;
    if (m < 1) { m = 12; y -= 1; }
    setViewYear(y);
    setViewMonth(m);
    notifyMonthChange(y, m);
  };

  const handleNextMonth = () => {
    let y = viewYear;
    let m = viewMonth + 1;
    if (m > 12) { m = 1; y += 1; }
    setViewYear(y);
    setViewMonth(m);
    notifyMonthChange(y, m);
  };

  // Click-outside to close
  useEffect(() => {
    if (!isOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [isOpen]);

  // Build calendar grid
  const firstDayOfWeek = new Date(viewYear, viewMonth - 1, 1).getDay(); // 0=Sun
  const daysInMonth = new Date(viewYear, viewMonth, 0).getDate();
  const daysInPrevMonth = new Date(viewYear, viewMonth - 1, 0).getDate();

  const cells: Array<{ dateStr: string; day: number; currentMonth: boolean }> = [];

  // Pad with previous month days
  for (let i = firstDayOfWeek - 1; i >= 0; i--) {
    const d = daysInPrevMonth - i;
    let prevM = viewMonth - 1;
    let prevY = viewYear;
    if (prevM < 1) { prevM = 12; prevY -= 1; }
    cells.push({ dateStr: toDateString(prevY, prevM, d), day: d, currentMonth: false });
  }

  // Current month days
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ dateStr: toDateString(viewYear, viewMonth, d), day: d, currentMonth: true });
  }

  // Pad with next month days
  const remaining = 42 - cells.length; // always 6 rows
  for (let d = 1; d <= remaining; d++) {
    let nextM = viewMonth + 1;
    let nextY = viewYear;
    if (nextM > 12) { nextM = 1; nextY += 1; }
    cells.push({ dateStr: toDateString(nextY, nextM, d), day: d, currentMonth: false });
  }

  const isNextMonthFuture = (() => {
    const ny = viewMonth === 12 ? viewYear + 1 : viewYear;
    const nm = viewMonth === 12 ? 1 : viewMonth + 1;
    return new Date(ny, nm - 1, 1) > today;
  })();

  const buttonLabel = selectedDate
    ? selectedDate.replace(/-/g, ".")
    : t("dashboard.tableClear.viewSnapshot");

  return (
    <div ref={containerRef} className="relative inline-block">
      {/* Trigger button */}
      <button
        onClick={handleOpen}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-label border transition-colors font-medium",
          selectedDate
            ? "border-primary/60 bg-primary/15 text-primary hover:bg-primary/20"
            : "border-border bg-secondary text-foreground hover:border-primary/40 hover:bg-secondary/80",
        )}
      >
        <CalendarDays className="h-3.5 w-3.5 shrink-0" />
        <span>{buttonLabel}</span>
      </button>

      {/* Dropdown calendar */}
      {isOpen && (
        <div className="absolute left-0 top-full mt-1 z-50 w-[280px] rounded-lg border border-border bg-card shadow-lg p-3 space-y-2">
          {/* "현재 기록으로" button — only when a date is selected */}
          {selectedDate && (
            <button
              onClick={() => { onSelect(null); setIsOpen(false); }}
              className="w-full text-left text-label text-primary/80 hover:text-primary px-1 py-0.5 rounded transition-colors"
            >
              {t("dashboard.tableClear.viewCurrent")}
            </button>
          )}

          {/* Month navigation */}
          <div className="flex items-center justify-between">
            <button
              onClick={handlePrevMonth}
              className="p-1 rounded hover:bg-secondary/50 text-muted-foreground hover:text-foreground transition-colors"
              aria-label="이전 달"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-label font-medium text-foreground">
              {viewYear}년 {pad2(viewMonth)}월
            </span>
            <button
              onClick={handleNextMonth}
              disabled={isNextMonthFuture}
              className={cn(
                "p-1 rounded transition-colors",
                isNextMonthFuture
                  ? "opacity-30 cursor-not-allowed text-muted-foreground"
                  : "hover:bg-secondary/50 text-muted-foreground hover:text-foreground",
              )}
              aria-label="다음 달"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          {/* Day headers */}
          <div className="grid grid-cols-7 text-center">
            {DAY_LABELS.map((label) => (
              <div key={label} className="text-caption text-muted-foreground py-1 font-medium">
                {label}
              </div>
            ))}
          </div>

          {/* Day grid */}
          <div className="grid grid-cols-7 gap-y-0.5">
            {cells.map(({ dateStr, day, currentMonth }) => {
              const isFuture = dateStr > todayStr;
              const isSelected = dateStr === selectedDate;
              const isToday = dateStr === todayStr;
              const hasDot = playRecordDates.has(dateStr);

              return (
                <button
                  key={dateStr}
                  disabled={isFuture}
                  onClick={() => {
                    if (isFuture) return;
                    onSelect(dateStr);
                    setIsOpen(false);
                  }}
                  className={cn(
                    "relative flex flex-col items-center justify-center rounded py-1 text-label transition-colors",
                    !currentMonth && "opacity-25",
                    isFuture && "opacity-40 cursor-not-allowed",
                    isSelected && "bg-primary/25 text-primary",
                    !isSelected && isToday && "text-primary font-medium",
                    !isSelected && !isFuture && currentMonth && "hover:bg-secondary/50",
                  )}
                >
                  <span>{day}</span>
                  {hasDot && (
                    <span
                      className={cn(
                        "absolute bottom-0.5 left-1/2 -translate-x-1/2 rounded-full w-1 h-1",
                        isSelected ? "bg-primary/60" : "bg-primary/40",
                      )}
                    />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
