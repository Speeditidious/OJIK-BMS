"use client";

import { useMemo } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { HeatmapDay, CourseActivityItem } from "@/hooks/use-analysis";

interface ActivityCalendarProps {
  data: HeatmapDay[];
  year: number;
  month: number; // 1-based
  onDayClick: (date: string) => void;
  onMonthChange: (year: number, month: number) => void;
  firstSyncDates?: { lr2?: string; beatoraja?: string };
  /** Per-client heatmap data — when both provided, dots are split by client */
  dataLr2?: HeatmapDay[];
  dataBeatoraja?: HeatmapDay[];
  courseData?: CourseActivityItem[];
}

const WEEKDAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"];


function toDateString(year: number, month: number, day: number): string {
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

interface DotItem {
  label: string;
  color: "primary" | "accent";
}

function getDotItems(
  dateStr: string,
  value: number,
  firstSyncDates?: { lr2?: string; beatoraja?: string },
  lr2Value?: number,
  beatorajaValue?: number,
  courseInfo?: { count: number; hasFirstClear: boolean },
): DotItem[] {
  const dots: DotItem[] = [];
  if (firstSyncDates?.lr2 === dateStr)
    dots.push({ label: "첫 동기화 (LR2)", color: "accent" });
  if (firstSyncDates?.beatoraja === dateStr)
    dots.push({ label: "첫 동기화 (Beatoraja)", color: "accent" });
  if (courseInfo) {
    const prefix = courseInfo.hasFirstClear ? "★ " : "";
    dots.push({ label: `${prefix}코스 클리어 ${courseInfo.count}건`, color: "accent" });
  }
  if (lr2Value !== undefined && beatorajaValue !== undefined) {
    if (lr2Value > 0) dots.push({ label: `${lr2Value}개 갱신 (LR2)`, color: "primary" });
    if (beatorajaValue > 0) dots.push({ label: `${beatorajaValue}개 갱신 (Beatoraja)`, color: "primary" });
  } else if (value > 0) {
    dots.push({ label: `${value}개 갱신`, color: "primary" });
  }
  return dots;
}

export function ActivityCalendar({
  data,
  year,
  month,
  onDayClick,
  onMonthChange,
  firstSyncDates,
  dataLr2,
  dataBeatoraja,
  courseData,
}: ActivityCalendarProps) {
  const today = new Date();
  const todayStr = toDateString(today.getFullYear(), today.getMonth() + 1, today.getDate());

  const valueMap = useMemo(() => {
    const map: Record<string, number> = {};
    for (const d of data) map[d.date] = d.value;
    return map;
  }, [data]);

  const lr2Map = useMemo(() => {
    if (!dataLr2) return undefined;
    const map: Record<string, number> = {};
    for (const d of dataLr2) map[d.date] = d.value;
    return map;
  }, [dataLr2]);

  const beatorajaMap = useMemo(() => {
    if (!dataBeatoraja) return undefined;
    const map: Record<string, number> = {};
    for (const d of dataBeatoraja) map[d.date] = d.value;
    return map;
  }, [dataBeatoraja]);

  const courseMap = useMemo(() => {
    if (!courseData?.length) return {} as Record<string, { count: number; hasFirstClear: boolean }>;
    const map: Record<string, { count: number; hasFirstClear: boolean }> = {};
    for (const c of courseData) {
      if (!c.date) continue;
      const existing = map[c.date] ?? { count: 0, hasFirstClear: false };
      existing.count++;
      if (c.is_first_clear) existing.hasFirstClear = true;
      map[c.date] = existing;
    }
    return map;
  }, [courseData]);

  // Build 6×7 grid
  const cells = useMemo(() => {
    const firstDay = new Date(year, month - 1, 1).getDay(); // 0=Sun
    const daysInMonth = new Date(year, month, 0).getDate();
    const grid: Array<{ day: number | null; dateStr: string | null }> = [];

    for (let i = 0; i < firstDay; i++) grid.push({ day: null, dateStr: null });
    for (let d = 1; d <= daysInMonth; d++) {
      grid.push({ day: d, dateStr: toDateString(year, month, d) });
    }
    while (grid.length < 42) grid.push({ day: null, dateStr: null });

    return grid;
  }, [year, month]);

  function prevMonth() {
    if (month === 1) onMonthChange(year - 1, 12);
    else onMonthChange(year, month - 1);
  }

  function nextMonth() {
    if (month === 12) onMonthChange(year + 1, 1);
    else onMonthChange(year, month + 1);
  }

  return (
    <div className="space-y-3">
      {/* Month navigation header */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="icon" onClick={prevMonth}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <span className="text-sm font-semibold">
          {year}년 {month}월
        </span>
        <Button variant="ghost" size="icon" onClick={nextMonth}>
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {/* Weekday labels */}
      <div className="grid grid-cols-7 gap-1">
        {WEEKDAY_LABELS.map((label) => (
          <div key={label} className="text-center text-xs text-muted-foreground font-medium py-1">
            {label}
          </div>
        ))}
      </div>

      {/* Date grid */}
      <div className="grid grid-cols-7 gap-1">
        {cells.map((cell, i) => {
          if (!cell.day || !cell.dateStr) {
            return <div key={i} />;
          }

          const dateStr = cell.dateStr;
          const value = valueMap[dateStr] ?? 0;
          const isToday = dateStr === todayStr;
const dots = getDotItems(
            dateStr,
            value,
            firstSyncDates,
            lr2Map?.[dateStr] ?? (lr2Map ? 0 : undefined),
            beatorajaMap?.[dateStr] ?? (beatorajaMap ? 0 : undefined),
            courseMap[dateStr],
          );

          return (
            <button
              key={dateStr}
              className={[
                "min-h-[88px] rounded-md flex flex-col items-center p-2 relative text-xs transition-colors",
                "hover:bg-accent/20",
                value > 0 || dots.length > 0 ? "font-medium" : "text-muted-foreground",
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={() => onDayClick(dateStr)}
              title={value > 0 ? `${cell.day}일 — ${value}건` : String(cell.day)}
            >
              {/* Date number top-left — badge on today */}
              {isToday ? (
                <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold leading-none mb-1">
                  {cell.day}
                </span>
              ) : (
                <span className="leading-none mb-1">{cell.day}</span>
              )}

              {/* Dot items */}
              {dots.length > 0 && (
                <div className="flex flex-col gap-0.5 w-full">
                  {dots.map((dot, di) => (
                    <div key={di} className="flex items-center gap-0.5 min-w-0">
                      <span
                        className="shrink-0 text-xs leading-none"
                        style={{ color: `hsl(var(--${dot.color}))` }}
                      >
                        ●
                      </span>
                      <span
                        className="text-xs leading-tight truncate"
                        style={{ color: `hsl(var(--${dot.color}))` }}
                      >
                        {dot.label}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
