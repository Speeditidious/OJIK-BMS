"use client";

import { useMemo } from "react";
import { HeatmapDay, ClientTypeFilter, CourseActivityItem } from "@/hooks/use-analysis";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ActivityHeatmapProps {
  data: HeatmapDay[];
  year: number;
  firstSyncDates?: { lr2?: string; beatoraja?: string };
  clientType?: ClientTypeFilter;
  courseData?: CourseActivityItem[];
}

const DAYS_OF_WEEK = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function getIntensityClass(value: number, max: number): string {
  if (value === 0 || max === 0) return "bg-card border border-border/30";
  const ratio = value / max;
  if (ratio < 0.25) return "bg-primary/20";
  if (ratio < 0.5) return "bg-primary/45";
  if (ratio < 0.75) return "bg-primary/70";
  return "bg-primary";
}

export function ActivityHeatmap({ data, year, firstSyncDates, clientType, courseData }: ActivityHeatmapProps) {
  const courseMap = useMemo<Record<string, { count: number; hasFirstClear: boolean }>>(() => {
    if (!courseData?.length) return {};
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

  const firstSyncMap = useMemo<Record<string, Array<"lr2" | "beatoraja">>>(() => {
    const map: Record<string, Array<"lr2" | "beatoraja">> = {};
    if (firstSyncDates?.lr2 && clientType !== "beatoraja") {
      map[firstSyncDates.lr2] = [...(map[firstSyncDates.lr2] ?? []), "lr2"];
    }
    if (firstSyncDates?.beatoraja && clientType !== "lr2") {
      map[firstSyncDates.beatoraja] = [...(map[firstSyncDates.beatoraja] ?? []), "beatoraja"];
    }
    return map;
  }, [firstSyncDates, clientType]);

  const { grid, monthLabels, maxValue } = useMemo(() => {
    const valueMap: Record<string, number> = {};
    let maxValue = 0;
    for (const d of data) {
      valueMap[d.date] = d.value;
      if (d.value > maxValue) maxValue = d.value;
    }

    // Build a 53-week x 7-day grid starting from Jan 1
    const startDate = new Date(year, 0, 1);
    const startDow = startDate.getDay(); // 0=Sun

    const cells: Array<{ date: string | null; value: number; week: number; dow: number }> = [];
    const monthLabelWeeks: Array<{ month: number; week: number }> = [];

    let currentMonth = -1;
    for (let week = 0; week < 53; week++) {
      for (let dow = 0; dow < 7; dow++) {
        const dayIndex = week * 7 + dow - startDow;
        if (dayIndex < 0 || dayIndex >= 366) {
          cells.push({ date: null, value: 0, week, dow });
          continue;
        }
        const d = new Date(year, 0, 1 + dayIndex);
        if (d.getFullYear() !== year) {
          cells.push({ date: null, value: 0, week, dow });
          continue;
        }
        const dateStr = d.toISOString().slice(0, 10);
        if (d.getMonth() !== currentMonth) {
          currentMonth = d.getMonth();
          monthLabelWeeks.push({ month: currentMonth, week });
        }
        cells.push({ date: dateStr, value: valueMap[dateStr] ?? 0, week, dow });
      }
    }

    return { grid: cells, monthLabels: monthLabelWeeks, maxValue };
  }, [data, year]);

  const rows = useMemo(() => {
    const r: (typeof grid)[] = Array.from({ length: 7 }, () => []);
    for (const cell of grid) {
      r[cell.dow].push(cell);
    }
    return r;
  }, [grid]);

  const totalWeeks = 53;

  return (
    <div className="w-full overflow-x-auto">
      <div className="inline-block min-w-max">
        {/* Month labels */}
        <div className="ml-8 mb-1">
          <div style={{ width: totalWeeks * 13 }} className="relative h-4">
            {monthLabels.map(({ month, week }) => (
              <span
                key={month}
                className="text-[10px] text-muted-foreground absolute top-0"
                style={{ left: week * 13 }}
              >
                {MONTHS[month]}
              </span>
            ))}
          </div>
        </div>

        {/* Grid */}
        <TooltipProvider delayDuration={200}>
          <div className="flex gap-0.5">
            {/* Day labels */}
            <div className="flex flex-col gap-0.5 mr-1">
              {DAYS_OF_WEEK.map((d, i) => (
                <div
                  key={d}
                  className="text-[10px] text-muted-foreground h-3 leading-3 w-6 text-right pr-1"
                  style={{ visibility: i % 2 === 1 ? "visible" : "hidden" }}
                >
                  {d}
                </div>
              ))}
            </div>

            {/* Week columns */}
            {Array.from({ length: totalWeeks }, (_, week) => (
              <div key={week} className="flex flex-col gap-0.5">
                {rows.map((row, dow) => {
                  const cell = row[week];
                  if (!cell || cell.date === null) {
                    return <div key={dow} className="w-3 h-3 rounded-[2px] opacity-0" />;
                  }
                  const syncClients = cell.date ? (firstSyncMap[cell.date] ?? []) : [];
                  const courseInfo = cell.date ? courseMap[cell.date] : undefined;

                  const isFirstSync = syncClients.length > 0;
                  const cellClass = `w-3 h-3 rounded-[2px] cursor-default transition-opacity hover:opacity-80 ${
                    isFirstSync
                      ? "bg-accent border border-accent"
                      : getIntensityClass(cell.value, maxValue)
                  }`;
                  const syncLabel = isFirstSync
                    ? syncClients.map((c) => (c === "lr2" ? "LR2" : "Beatoraja")).join(" + ") + " 첫 동기화"
                    : null;

                  return (
                    <Tooltip key={dow}>
                      <TooltipTrigger asChild>
                        <div className="relative w-3 h-3">
                          <div className={cellClass} style={{ width: "100%", height: "100%" }} />
                          {courseInfo && (
                            <span
                              className="absolute bottom-0 right-0 w-1.5 h-1.5 rounded-full border border-background"
                              style={{
                                backgroundColor: courseInfo.hasFirstClear
                                  ? "hsl(var(--accent))"
                                  : "hsl(var(--accent)/0.7)",
                              }}
                            />
                          )}
                        </div>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="font-medium text-xs">{cell.date}</p>
                        {syncLabel ? (
                          <p className="text-xs text-muted-foreground">{syncLabel}</p>
                        ) : (
                          <p className="text-xs text-muted-foreground">{cell.value} 기록 갱신</p>
                        )}
                        {courseInfo && (
                          <p className="text-xs" style={{ color: "hsl(var(--accent))" }}>
                            {courseInfo.hasFirstClear ? "★ " : ""}코스 클리어 {courseInfo.count}건
                          </p>
                        )}
                      </TooltipContent>
                    </Tooltip>
                  );
                })}
              </div>
            ))}
          </div>
        </TooltipProvider>

        {/* Legend */}
        <div className="flex items-center gap-3 mt-2 ml-8 text-[10px] text-muted-foreground flex-wrap">
          <div className="flex items-center gap-1">
            <span>Less</span>
            {[0, 0.25, 0.5, 0.75, 1].map((ratio) => (
              <div
                key={ratio}
                className={`w-3 h-3 rounded-[2px] ${getIntensityClass(ratio * maxValue, maxValue)}`}
              />
            ))}
            <span>More</span>
          </div>
          {Object.keys(firstSyncMap).length > 0 && (
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-[2px] bg-accent border border-accent" />
              <span>첫 동기화</span>
            </div>
          )}
          {Object.keys(courseMap).length > 0 && (
            <div className="flex items-center gap-1">
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: "hsl(var(--accent))" }}
              />
              <span>코스 클리어</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
