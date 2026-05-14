"use client";

import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { HeatmapDay, CourseActivityItem } from "@/hooks/use-analysis";
import { localeFromLanguage } from "@/lib/i18n/locale";

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
  ratingUpdatesData?: Array<{ date: string; count: number }>;
}

function buildWeekdayLabels(locale: string): string[] {
  const formatter = new Intl.DateTimeFormat(locale, { weekday: "short" });
  // 2024-01-07 is a Sunday; use it as a stable reference for Sun..Sat.
  return Array.from({ length: 7 }, (_, i) => formatter.format(new Date(Date.UTC(2024, 0, 7 + i))));
}

function toDateString(year: number, month: number, day: number): string {
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

interface DotItem {
  label: string;
  color: "primary" | "accent" | "play" | "new-play" | "rating";
}

function getDotItems(
  dateStr: string,
  updates: number,
  newPlays: number,
  plays: number,
  ratingUpdates: number,
  t: (key: string, opts?: Record<string, unknown>) => string,
  firstSyncDates?: { lr2?: string; beatoraja?: string },
  lr2Updates?: number,
  lr2NewPlays?: number,
  lr2Plays?: number,
  beatorajaUpdates?: number,
  beatorajaNewPlays?: number,
  beatorajaPlays?: number,
  courseInfo?: { count: number; hasFirstClear: boolean },
): DotItem[] {
  const dots: DotItem[] = [];
  if (firstSyncDates?.lr2 === dateStr)
    dots.push({ label: `LR2 ${t("dashboard.activity.firstSync")}`, color: "accent" });
  if (firstSyncDates?.beatoraja === dateStr)
    dots.push({ label: `Beatoraja ${t("dashboard.activity.firstSync")}`, color: "accent" });
  if (courseInfo) {
    const prefix = courseInfo.hasFirstClear ? "★ " : "";
    dots.push({ label: `${prefix}${t("dashboard.activity.courseClear", { count: courseInfo.count })}`, color: "accent" });
  }
  if (lr2Updates !== undefined && beatorajaUpdates !== undefined) {
    if (lr2Updates > 0) dots.push({ label: `${t("dashboard.activity.scoreUpdates", { count: lr2Updates })} (LR2)`, color: "primary" });
    if (beatorajaUpdates > 0) dots.push({ label: `${t("dashboard.activity.scoreUpdates", { count: beatorajaUpdates })} (Beatoraja)`, color: "primary" });
    if ((lr2NewPlays ?? 0) > 0) dots.push({ label: `${t("dashboard.activity.newPlays", { count: lr2NewPlays })} (LR2)`, color: "new-play" });
    if ((beatorajaNewPlays ?? 0) > 0) dots.push({ label: `${t("dashboard.activity.newPlays", { count: beatorajaNewPlays })} (Beatoraja)`, color: "new-play" });
    if ((lr2Plays ?? 0) > 0) dots.push({ label: `${t("dashboard.activity.plays", { count: lr2Plays })} (LR2)`, color: "play" });
    if ((beatorajaPlays ?? 0) > 0) dots.push({ label: `${t("dashboard.activity.plays", { count: beatorajaPlays })} (Beatoraja)`, color: "play" });
  } else {
    if (updates > 0) dots.push({ label: t("dashboard.activity.scoreUpdates", { count: updates }), color: "primary" });
    if (newPlays > 0) dots.push({ label: t("dashboard.activity.newPlays", { count: newPlays }), color: "new-play" });
    if (plays > 0) dots.push({ label: t("dashboard.activity.plays", { count: plays }), color: "play" });
  }
  const isFirstSync = firstSyncDates?.lr2 === dateStr || firstSyncDates?.beatoraja === dateStr;
  if (!isFirstSync && ratingUpdates > 0) {
    dots.push({ label: t("dashboard.activity.ratingUpdates", { count: ratingUpdates }), color: "rating" });
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
  ratingUpdatesData,
}: ActivityCalendarProps) {
  const { t, i18n } = useTranslation();
  const dateLocale = localeFromLanguage(i18n.language);
  const weekdayLabels = useMemo(() => buildWeekdayLabels(dateLocale), [dateLocale]);
  const monthYearLabel = useMemo(
    () => new Date(year, month - 1, 1).toLocaleDateString(dateLocale, { year: "numeric", month: "long" }),
    [year, month, dateLocale],
  );
  const today = new Date();
  const todayStr = toDateString(today.getFullYear(), today.getMonth() + 1, today.getDate());

  const updatesMap = useMemo(() => {
    const map: Record<string, number> = {};
    for (const d of data) map[d.date] = d.updates;
    return map;
  }, [data]);

  const newPlaysMap = useMemo(() => {
    const map: Record<string, number> = {};
    for (const d of data) map[d.date] = d.new_plays ?? 0;
    return map;
  }, [data]);

  const playsMap = useMemo(() => {
    const map: Record<string, number> = {};
    for (const d of data) map[d.date] = d.plays;
    return map;
  }, [data]);

  const ratingUpdatesMap = useMemo(() => {
    const map: Record<string, number> = {};
    for (const item of ratingUpdatesData ?? []) {
      map[item.date] = item.count;
    }
    return map;
  }, [ratingUpdatesData]);

  const lr2UpdatesMap = useMemo(() => {
    if (!dataLr2) return undefined;
    const map: Record<string, number> = {};
    for (const d of dataLr2) map[d.date] = d.updates;
    return map;
  }, [dataLr2]);

  const lr2NewPlaysMap = useMemo(() => {
    if (!dataLr2) return undefined;
    const map: Record<string, number> = {};
    for (const d of dataLr2) map[d.date] = d.new_plays ?? 0;
    return map;
  }, [dataLr2]);

  const lr2PlaysMap = useMemo(() => {
    if (!dataLr2) return undefined;
    const map: Record<string, number> = {};
    for (const d of dataLr2) map[d.date] = d.plays;
    return map;
  }, [dataLr2]);

  const beatorajaUpdatesMap = useMemo(() => {
    if (!dataBeatoraja) return undefined;
    const map: Record<string, number> = {};
    for (const d of dataBeatoraja) map[d.date] = d.updates;
    return map;
  }, [dataBeatoraja]);

  const beatorajaNewPlaysMap = useMemo(() => {
    if (!dataBeatoraja) return undefined;
    const map: Record<string, number> = {};
    for (const d of dataBeatoraja) map[d.date] = d.new_plays ?? 0;
    return map;
  }, [dataBeatoraja]);

  const beatorajaPlaysMap = useMemo(() => {
    if (!dataBeatoraja) return undefined;
    const map: Record<string, number> = {};
    for (const d of dataBeatoraja) map[d.date] = d.plays;
    return map;
  }, [dataBeatoraja]);

  const courseMap = useMemo(() => {
    if (!courseData?.length) return {} as Record<string, { count: number; hasFirstClear: boolean }>;
    const map: Record<string, { count: number; hasFirstClear: boolean }> = {};
    for (const c of courseData) {
      if (!c.date) continue;
      const existing = map[c.date] ?? { count: 0, hasFirstClear: false };
      existing.count++;
      existing.hasFirstClear = true; // backend only returns first clears
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
        <span className="text-body font-semibold">
          {monthYearLabel}
        </span>
        <Button variant="ghost" size="icon" onClick={nextMonth}>
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {/* Weekday labels */}
      <div className="grid grid-cols-7 gap-1">
        {weekdayLabels.map((label, i) => (
          <div key={i} className="text-center text-label text-muted-foreground font-medium py-1">
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
          const updates = updatesMap[dateStr] ?? 0;
          const newPlays = newPlaysMap[dateStr] ?? 0;
          const plays = playsMap[dateStr] ?? 0;
          const ratingUpdates = ratingUpdatesMap[dateStr] ?? 0;
          const isToday = dateStr === todayStr;
          const cellIsFirstSync = firstSyncDates?.lr2 === dateStr || firstSyncDates?.beatoraja === dateStr;
          const dots = getDotItems(
            dateStr,
            updates,
            newPlays,
            plays,
            ratingUpdates,
            t,
            firstSyncDates,
            lr2UpdatesMap?.[dateStr] ?? (lr2UpdatesMap ? 0 : undefined),
            lr2NewPlaysMap?.[dateStr] ?? (lr2NewPlaysMap ? 0 : undefined),
            lr2PlaysMap?.[dateStr] ?? (lr2PlaysMap ? 0 : undefined),
            beatorajaUpdatesMap?.[dateStr] ?? (beatorajaUpdatesMap ? 0 : undefined),
            beatorajaNewPlaysMap?.[dateStr] ?? (beatorajaNewPlaysMap ? 0 : undefined),
            beatorajaPlaysMap?.[dateStr] ?? (beatorajaPlaysMap ? 0 : undefined),
            courseMap[dateStr],
          );

          return (
            <button
              key={dateStr}
              className={[
                "min-h-[88px] rounded-md flex flex-col items-center p-2 relative text-label transition-colors",
                "hover:bg-accent/20",
                updates > 0 || plays > 0 || ratingUpdates > 0 || dots.length > 0 ? "font-medium" : "text-muted-foreground",
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={() => onDayClick(dateStr)}
              title={updates > 0 || newPlays > 0 || (!cellIsFirstSync && ratingUpdates > 0) ? `${cell.day} — ${t("dashboard.activity.scoreUpdates", { count: updates })} / ${t("dashboard.activity.newPlays", { count: newPlays })}${!cellIsFirstSync && ratingUpdates > 0 ? ` / ${t("dashboard.activity.ratingUpdates", { count: ratingUpdates })}` : ""}` : plays > 0 ? `${cell.day} — ${t("dashboard.activity.plays", { count: plays })}` : String(cell.day)}
            >
              {/* Date number top-left — badge on today */}
              {isToday ? (
                <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-body font-bold leading-none mb-1">
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
                        className="shrink-0 text-label leading-none"
                        style={{ color: dot.color === "play" ? "hsl(var(--chart-play))" : dot.color === "new-play" ? "hsl(var(--chart-new-play))" : dot.color === "rating" ? "hsl(var(--chart-rating))" : `hsl(var(--${dot.color}))` }}
                      >
                        ●
                      </span>
                      <span
                        className="text-label leading-tight truncate"
                        style={{ color: dot.color === "play" ? "hsl(var(--chart-play))" : dot.color === "new-play" ? "hsl(var(--chart-new-play))" : dot.color === "rating" ? "hsl(var(--chart-rating))" : `hsl(var(--${dot.color}))` }}
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
