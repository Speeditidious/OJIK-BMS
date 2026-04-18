"use client";

import { useMemo } from "react";
import {
  Line,
  LineChart,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useChartWidth } from "@/hooks/use-chart-size";
import { ActivityDay, ClientTypeFilter, CourseActivityItem } from "@/hooks/use-analysis";

export type ActivitySeries = "updates" | "plays" | "new_plays" | "rating_updates";

interface ActivityBarChartProps {
  data: ActivityDay[];
  firstSyncDates?: { lr2?: string; beatoraja?: string };
  clientType?: ClientTypeFilter;
  courseData?: CourseActivityItem[];
  activeModes?: ActivitySeries[];
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function seriesColor(mode: ActivitySeries): string {
  if (mode === "plays") return "hsl(var(--chart-play))";
  if (mode === "new_plays") return "hsl(var(--chart-new-play))";
  if (mode === "rating_updates") return "hsl(var(--warning))";
  return "hsl(var(--primary))";
}

function seriesLabel(mode: ActivitySeries): string {
  if (mode === "plays") return "플레이";
  if (mode === "new_plays") return "신규 기록";
  if (mode === "rating_updates") return "레이팅 갱신";
  return "갱신 기록";
}

function SyncLabel({ viewBox, labels }: { viewBox?: { x: number; y: number }; labels: string[] }) {
  if (!viewBox) return null;
  return (
    <g>
      {labels.map((label, i) => (
        <text
          key={label}
          x={viewBox.x + 4}
          y={viewBox.y + 12 + i * 12}
          fill="hsl(var(--accent))"
          fontSize="var(--text-caption)"
          textAnchor="start"
        >
          {label}
        </text>
      ))}
    </g>
  );
}

function ChartTooltip({
  active,
  payload,
  activeModes,
}: {
  active?: boolean;
  payload?: any[];
  activeModes: ActivitySeries[];
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload as {
    fullDate: string;
    updates: number;
    new_plays: number;
    plays: number;
    rating_updates: number;
    syncLabels?: string[];
    hideSyncCount?: boolean;
    courseLabels?: string[];
  };
  const hasAnySyncLabel = row.syncLabels?.length;
  const showCounts = !row.hideSyncCount || row.courseLabels?.length;
  return (
    <div
      style={{
        backgroundColor: "hsl(var(--card))",
        border: "1px solid hsl(var(--border))",
        borderRadius: "6px",
        fontSize: "var(--text-label)",
        color: "hsl(var(--foreground))",
        padding: "8px 10px",
      }}
    >
      <p style={{ marginBottom: (hasAnySyncLabel || row.courseLabels?.length) ? 4 : 0 }}>{row.fullDate}</p>
      {row.syncLabels?.map((label) => (
        <p key={label} style={{ color: "hsl(var(--accent))", margin: 0 }}>
          {label}
        </p>
      ))}
      {row.courseLabels?.map((label) => (
        <p key={label} style={{ color: "hsl(var(--accent))", margin: 0 }}>
          {label}
        </p>
      ))}
      {showCounts && activeModes.map((mode) => {
        const value = row[mode];
        if (value <= 0) return null;
        return (
          <p
            key={mode}
            style={{
              margin: 0,
              marginTop: (hasAnySyncLabel || row.courseLabels?.length) ? 4 : 0,
              color: seriesColor(mode),
              fontWeight: 600,
            }}
          >
            {seriesLabel(mode)}: {mode === "plays" ? `${value}회` : `${value}건`}
          </p>
        );
      })}
    </div>
  );
}

export function ActivityBarChart({
  data,
  firstSyncDates,
  clientType,
  courseData,
  activeModes = ["updates"] as ActivitySeries[],
}: ActivityBarChartProps) {
  const [chartRef, chartWidth] = useChartWidth(150);
  const enabledModes = useMemo<ActivitySeries[]>(
    () => (activeModes.length > 0 ? activeModes : ["updates"]),
    [activeModes],
  );

  const syncByDate = useMemo(() => {
    const map: Record<string, { labels: string[]; hideCount: boolean }> = {};
    if (!firstSyncDates) return map;
    if (clientType !== "beatoraja" && firstSyncDates.lr2) {
      const prev = map[firstSyncDates.lr2] ?? { labels: [], hideCount: true };
      prev.labels.push("LR2 첫 동기화");
      map[firstSyncDates.lr2] = prev;
    }
    if (clientType !== "lr2" && firstSyncDates.beatoraja) {
      const prev = map[firstSyncDates.beatoraja] ?? { labels: [], hideCount: true };
      prev.labels.push("Beatoraja 첫 동기화");
      prev.hideCount = false;
      map[firstSyncDates.beatoraja] = prev;
    }
    return map;
  }, [firstSyncDates, clientType]);

  const courseByDate = useMemo(() => {
    if (!courseData?.length) return {} as Record<string, string[]>;
    const map: Record<string, string[]> = {};
    for (const course of courseData) {
      if (!course.date) continue;
      const label = course.course_name
        ? (course.dan_title ? `[${course.dan_title}] ` : "") + course.course_name
        : `코스 (${course.course_hash.slice(0, 6)}…)`;
      (map[course.date] ??= []).push(label);
    }
    return map;
  }, [courseData]);

  const chartData = useMemo(() => {
    const seenDates = new Set(data.map((day) => day.date));
    const injected = [...data];
    const rangeMin = data.length > 0 ? data[0].date : null;
    for (const date of Object.keys(syncByDate)) {
      if (!seenDates.has(date) && (rangeMin === null || date >= rangeMin)) {
        injected.push({ date, updates: 0, new_plays: 0, plays: 0, rating_updates: 0 });
        seenDates.add(date);
      }
    }
    for (const date of Object.keys(courseByDate)) {
      if (!seenDates.has(date) && (rangeMin === null || date >= rangeMin)) {
        injected.push({ date, updates: 0, new_plays: 0, plays: 0, rating_updates: 0 });
        seenDates.add(date);
      }
    }
    injected.sort((left, right) => left.date.localeCompare(right.date));
    return injected.map((day) => ({
      date: formatDate(day.date),
      fullDate: day.date,
      updates: day.updates,
      new_plays: day.new_plays ?? 0,
      plays: day.plays,
      rating_updates: day.rating_updates ?? 0,
      syncLabels: syncByDate[day.date]?.labels,
      hideSyncCount: syncByDate[day.date]?.hideCount ?? false,
      courseLabels: courseByDate[day.date],
    }));
  }, [courseByDate, data, syncByDate]);

  const yMax = useMemo(() => {
    const values = chartData.flatMap((row) =>
      enabledModes.map((mode) => {
        if (mode === "plays") return row.plays ?? 0;
        if (mode === "new_plays") return row.new_plays ?? 0;
        if (mode === "rating_updates") return row.rating_updates ?? 0;
        return row.updates ?? 0;
      }),
    );
    return Math.max(1, ...values);
  }, [chartData, enabledModes]);

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground text-body">
        이 기간에 동기화된 데이터가 없습니다
      </div>
    );
  }

  if (chartWidth === 0) {
    return <div ref={chartRef} style={{ width: "100%", height: 200 }} />;
  }

  const minDate = chartData[0].fullDate;
  const maxDate = chartData[chartData.length - 1].fullDate;

  return (
    <div ref={chartRef}>
      <LineChart width={chartWidth} height={200} data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <XAxis
          dataKey="date"
          tick={{ fontSize: "var(--text-caption)", fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          domain={[0, yMax]}
          tick={{ fontSize: "var(--text-caption)", fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
        />
        <Tooltip
          content={<ChartTooltip activeModes={enabledModes} />}
          cursor={{ stroke: "hsl(var(--accent))", strokeWidth: 1 }}
        />
        {enabledModes.map((mode) => (
          <Line
            key={mode}
            type="monotone"
            dataKey={mode}
            stroke={seriesColor(mode)}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 3, fill: seriesColor(mode) }}
          />
        ))}
        {Object.entries(syncByDate)
          .filter(([date]) => date >= minDate && date <= maxDate)
          .map(([date, meta]) => (
            <ReferenceLine
              key={`sync-${date}`}
              x={formatDate(date)}
              stroke="hsl(var(--accent))"
              strokeDasharray="4 3"
              strokeWidth={1.5}
              label={
                meta.labels.length === 1
                  ? { value: meta.labels[0], position: "insideTopRight", fontSize: "var(--text-caption)", fill: "hsl(var(--accent))" }
                  : <SyncLabel labels={meta.labels} />
              }
            />
          ))}
        {Object.entries(courseByDate)
          .filter(([date]) => date >= minDate && date <= maxDate)
          .map(([date]) => (
            <ReferenceLine
              key={`course-${date}`}
              x={formatDate(date)}
              stroke="hsl(var(--accent)/0.6)"
              strokeDasharray="2 2"
              strokeWidth={1}
            />
          ))}
      </LineChart>
    </div>
  );
}
