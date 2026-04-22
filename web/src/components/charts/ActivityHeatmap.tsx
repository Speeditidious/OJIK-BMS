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
  viewMode?: "updates" | "plays" | "new_plays" | "rating_updates";
}

const DAYS_OF_WEEK = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function getIntensityClass(value: number, max: number, mode: "updates" | "plays" | "new_plays" | "rating_updates" = "updates"): string {
  if (value === 0 || max === 0) return "bg-border/30";
  const ratio = value / max;
  if (mode === "plays") {
    if (ratio < 0.25) return "bg-[hsl(var(--chart-play)/0.20)]";
    if (ratio < 0.5)  return "bg-[hsl(var(--chart-play)/0.45)]";
    if (ratio < 0.75) return "bg-[hsl(var(--chart-play)/0.70)]";
    return "bg-[hsl(var(--chart-play))]";
  }
  if (mode === "new_plays") {
    // new_plays uses --primary (lime) to match ActivityBarChart color re-mapping
    if (ratio < 0.25) return "bg-primary/20";
    if (ratio < 0.5)  return "bg-primary/45";
    if (ratio < 0.75) return "bg-primary/70";
    return "bg-primary";
  }
  if (mode === "rating_updates") {
    // rating_updates uses --chart-rating (most prominent)
    if (ratio < 0.25) return "bg-[hsl(var(--chart-rating)/0.20)]";
    if (ratio < 0.5)  return "bg-[hsl(var(--chart-rating)/0.45)]";
    if (ratio < 0.75) return "bg-[hsl(var(--chart-rating)/0.70)]";
    return "bg-[hsl(var(--chart-rating))]";
  }
  // updates uses --warning (orange)
  if (ratio < 0.25) return "bg-[hsl(var(--warning)/0.20)]";
  if (ratio < 0.5)  return "bg-[hsl(var(--warning)/0.45)]";
  if (ratio < 0.75) return "bg-[hsl(var(--warning)/0.70)]";
  return "bg-[hsl(var(--warning))]";
}

interface CellData {
  date: string;
  updates: number;
  new_plays: number;
  plays: number;
  rating_updates: number;
}

interface ColumnData {
  cells: (CellData | null)[];
}

interface MonthGroup {
  month: number;
  columns: ColumnData[];
}

export function ActivityHeatmap({ data, year, firstSyncDates, clientType, courseData, viewMode = "updates" }: ActivityHeatmapProps) {
  const courseMap = useMemo<Record<string, { count: number; hasFirstClear: boolean }>>(() => {
    if (!courseData?.length) return {};
    const map: Record<string, { count: number; hasFirstClear: boolean }> = {};
    for (const c of courseData) {
      if (!c.date) continue;
      const existing = map[c.date] ?? { count: 0, hasFirstClear: false };
      existing.count++;
      // hasFirstClear no longer tracked server-side
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

  const { monthGroups, maxValue } = useMemo(() => {
    const updatesMap: Record<string, number> = {};
    const newPlaysMap: Record<string, number> = {};
    const playsMap: Record<string, number> = {};
    const ratingUpdatesMap: Record<string, number> = {};
    let maxValue = 0;
    for (const d of data) {
      updatesMap[d.date] = d.updates;
      newPlaysMap[d.date] = d.new_plays ?? 0;
      playsMap[d.date] = d.plays;
      ratingUpdatesMap[d.date] = d.rating_updates ?? 0;
      const activeVal = viewMode === "plays"
        ? d.plays
        : viewMode === "new_plays"
          ? (d.new_plays ?? 0)
          : viewMode === "rating_updates"
            ? (d.rating_updates ?? 0)
            : d.updates;
      if (activeVal > maxValue) maxValue = activeVal;
    }

    const startDate = new Date(year, 0, 1);
    const startDow = startDate.getDay(); // 0=Sun

    // Initialize 12 month groups
    const groups: MonthGroup[] = Array.from({ length: 12 }, (_, i) => ({ month: i, columns: [] }));

    for (let week = 0; week < 53; week++) {
      // Build cells for this week, tracking which month each cell belongs to
      type WeekCell = (CellData & { month: number }) | null;
      const weekCells: WeekCell[] = [];

      for (let dow = 0; dow < 7; dow++) {
        const dayIndex = week * 7 + dow - startDow;
        if (dayIndex < 0 || dayIndex >= 366) {
          weekCells.push(null);
          continue;
        }
        const d = new Date(year, 0, 1 + dayIndex);
        if (d.getFullYear() !== year) {
          weekCells.push(null);
          continue;
        }
        const dateStr = d.toISOString().slice(0, 10);
        weekCells.push({
          date: dateStr,
          updates: updatesMap[dateStr] ?? 0,
          new_plays: newPlaysMap[dateStr] ?? 0,
          plays: playsMap[dateStr] ?? 0,
          rating_updates: ratingUpdatesMap[dateStr] ?? 0,
          month: d.getMonth(),
        });
      }

      // Find unique months present in this week (in order of first appearance)
      const monthsInWeek = new Set<number>();
      for (const cell of weekCells) {
        if (cell !== null) monthsInWeek.add(cell.month);
      }

      // For each month present, add a column to that month's group
      // with only that month's cells; other slots become null (transparent)
      for (const m of monthsInWeek) {
        const col: ColumnData = {
          cells: weekCells.map((cell) => {
            if (cell === null || cell.month !== m) return null;
            return {
              date: cell.date,
              updates: cell.updates,
              new_plays: cell.new_plays,
              plays: cell.plays,
              rating_updates: cell.rating_updates,
            };
          }),
        };
        groups[m].columns.push(col);
      }
    }

    return { monthGroups: groups, maxValue };
  }, [data, year, viewMode]);

  return (
    <div className="w-full overflow-x-auto">
      <div className="inline-block min-w-max">
        <TooltipProvider delayDuration={200}>
          <div className="flex">
            {/* Day labels column — padded to align with cells (below month label row) */}
            <div className="flex flex-col gap-0.5 mr-1" style={{ paddingTop: "20px" }}>
              {DAYS_OF_WEEK.map((d, i) => (
                <div
                  key={d}
                  className="text-caption text-foreground h-3 leading-3 w-6 text-right pr-1"
                  style={{ visibility: i % 2 === 1 ? "visible" : "hidden" }}
                >
                  {d}
                </div>
              ))}
            </div>

            {/* Month groups */}
            <div className="flex gap-3">
              {monthGroups.map(({ month, columns }) => (
                <div key={month}>
                  {/* Month label — normal flow, always above its own columns */}
                  <div className="text-caption text-foreground mb-1 h-4 leading-4">
                    {MONTHS[month]}
                  </div>
                  {/* Week columns for this month */}
                  <div className="flex gap-0.5">
                    {columns.map((col, ci) => (
                      <div key={ci} className="flex flex-col gap-0.5">
                        {col.cells.map((cell, dow) => {
                          if (cell === null) {
                            return <div key={dow} className="w-3 h-3 rounded-[2px] opacity-0" />;
                          }

                          const syncClients = firstSyncMap[cell.date] ?? [];
                          const courseInfo = courseMap[cell.date];
                          const isFirstSync = syncClients.length > 0;
                          // First-sync date: force activeVal to 0 for all viewModes (§4.5 / review §1.2)
                          const rawVal = viewMode === "plays"
                            ? cell.plays
                            : viewMode === "new_plays"
                              ? cell.new_plays
                              : viewMode === "rating_updates"
                                ? cell.rating_updates
                                : cell.updates;
                          const activeVal = isFirstSync ? 0 : rawVal;
                          const cellClass = `w-3 h-3 rounded-[2px] cursor-default transition-opacity hover:opacity-80 ${
                            isFirstSync
                              ? "bg-accent border border-accent"
                              : getIntensityClass(activeVal, maxValue, viewMode)
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
                                <p className="font-medium text-label">{cell.date}</p>
                                {syncLabel ? (
                                  <p className="text-label text-muted-foreground">{syncLabel}</p>
                                ) : activeVal === 0 && cell.updates === 0 && cell.new_plays === 0 && cell.plays === 0 && cell.rating_updates === 0 ? (
                                  <p className="text-label text-muted-foreground">기록 없음</p>
                                ) : (
                                  <>
                                    <p className="text-label" style={{ color: viewMode === "plays" ? "hsl(var(--chart-play))" : viewMode === "new_plays" ? "hsl(var(--primary))" : viewMode === "rating_updates" ? "hsl(var(--chart-rating))" : "hsl(var(--warning))" }}>
                                      {viewMode === "plays"
                                        ? `${cell.plays} 플레이`
                                        : viewMode === "new_plays"
                                          ? `${cell.new_plays} 신규 기록`
                                          : viewMode === "rating_updates"
                                            ? `${cell.rating_updates} 레이팅 갱신`
                                            : `${cell.updates} 갱신 기록`}
                                    </p>
                                    {viewMode === "new_plays" && cell.updates > 0 && (
                                      <p className="text-label text-muted-foreground">{cell.updates} 갱신 기록</p>
                                    )}
                                    {viewMode !== "rating_updates" && cell.rating_updates > 0 && (
                                      <p className="text-label" style={{ color: "hsl(var(--chart-rating))" }}>{cell.rating_updates} 레이팅 갱신</p>
                                    )}
                                    {viewMode !== "new_plays" && cell.new_plays > 0 && (
                                      <p className="text-label" style={{ color: "hsl(var(--primary))" }}>{cell.new_plays} 신규 기록</p>
                                    )}
                                    {viewMode === "plays" && cell.updates > 0 && (
                                      <p className="text-label text-muted-foreground">{cell.updates} 갱신 기록</p>
                                    )}
                                    {viewMode === "updates" && cell.plays > 0 && (
                                      <p className="text-label text-muted-foreground">{cell.plays} 플레이</p>
                                    )}
                                    {viewMode === "new_plays" && cell.plays > 0 && (
                                      <p className="text-label text-muted-foreground">{cell.plays} 플레이</p>
                                    )}
                                  </>
                                )}
                                {courseInfo && (
                                  <p className="text-label" style={{ color: "hsl(var(--accent))" }}>
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
                </div>
              ))}
            </div>
          </div>
        </TooltipProvider>

        {/* Legend */}
        <div className="flex items-center gap-3 mt-2 ml-7 text-caption text-muted-foreground flex-wrap">
          <div className="flex items-center gap-1">
            <span>Less</span>
            {[0, 0.25, 0.5, 0.75, 1].map((ratio) => (
              <div
                key={ratio}
                className={`w-3 h-3 rounded-[2px] ${getIntensityClass(ratio * (maxValue || 1), maxValue || 1, viewMode)}`}
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
