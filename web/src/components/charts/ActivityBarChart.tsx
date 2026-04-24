"use client";

import { useEffect, useMemo, useRef } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useChartWidth } from "@/hooks/use-chart-size";
import { ActivityDay, ClientTypeFilter, CourseActivityItem } from "@/hooks/use-analysis";
import { ChartLegend, type LegendItem } from "@/components/charts/ChartLegend";
import { daysInRange, type DateRange } from "@/lib/date-range";
import { pickTickResolution, formatTick, computeTicks } from "@/lib/axis-format";
import { formatCompactNumber } from "@/lib/rating-format";
import { ACTIVITY_CATEGORIES } from "@/lib/activity-categories";
import { niceTicks } from "@/lib/axis-ticks";

export type ActivitySeries = "updates" | "plays" | "new_plays" | "rating_updates";

interface ActivityBarChartProps {
  data: ActivityDay[];
  firstSyncDates?: { lr2?: string; beatoraja?: string };
  clientType?: ClientTypeFilter;
  courseData?: CourseActivityItem[];
  activeModes?: ActivitySeries[];
  rangeFrom?: string;
  rangeTo?: string;
}

// Color order: rating_updates (most prominent) > updates > new_plays > plays (least)
function seriesColor(mode: ActivitySeries): string {
  if (mode === "rating_updates") return "hsl(var(--chart-rating))";
  if (mode === "updates") return "hsl(var(--warning))";
  if (mode === "new_plays") return "hsl(var(--primary))";
  return "hsl(var(--chart-play))";
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
  rangeFrom,
  rangeTo,
}: ActivityBarChartProps) {
  const [chartRef, chartWidth] = useChartWidth(150);
  const enabledModes = useMemo<ActivitySeries[]>(() => {
    const set = new Set<string>(activeModes.length > 0 ? activeModes : ["updates"]);
    return ACTIVITY_CATEGORIES
      .map((cat) => cat.key)
      .filter((key): key is ActivitySeries => set.has(key));
  }, [activeModes]);

  // Only animate a <Line> on the render where it newly appears — existing lines
  // stay static when other toggles change, and removed lines just unmount.
  const mountedModesRef = useRef<Set<ActivitySeries>>(new Set());
  const newlyAdded = useMemo<Set<ActivitySeries>>(() => {
    const set = new Set<ActivitySeries>();
    for (const mode of enabledModes) {
      if (!mountedModesRef.current.has(mode)) set.add(mode);
    }
    return set;
  }, [enabledModes]);
  useEffect(() => {
    mountedModesRef.current = new Set(enabledModes);
  }, [enabledModes]);

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
    return injected.map((day) => {
      // First-sync date: zero out all counts including rating_updates (§4.2/4.5)
      const isFirstSync = syncByDate[day.date]?.hideCount ?? false;
      return {
        date: day.date,
        fullDate: day.date,
        updates: isFirstSync ? 0 : day.updates,
        new_plays: isFirstSync ? 0 : (day.new_plays ?? 0),
        plays: isFirstSync ? 0 : day.plays,
        rating_updates: isFirstSync ? 0 : (day.rating_updates ?? 0),
        syncLabels: syncByDate[day.date]?.labels,
        hideSyncCount: syncByDate[day.date]?.hideCount ?? false,
        courseLabels: courseByDate[day.date],
      };
    });
  }, [courseByDate, data, syncByDate]);

  const { dataMin: yMin, dataMax: yMax, yTicks } = useMemo(() => {
    const values = chartData.flatMap((row) =>
      enabledModes.map((mode) => {
        if (mode === "plays") return row.plays ?? 0;
        if (mode === "new_plays") return row.new_plays ?? 0;
        if (mode === "rating_updates") return row.rating_updates ?? 0;
        return row.updates ?? 0;
      }),
    );
    const dataMin = Math.min(...values);
    const dataMax = Math.max(...values);
    const flat = dataMin === dataMax;
    const domainMin = flat ? dataMin - 1 : dataMin;
    const domainMax = flat ? dataMax + 1 : dataMax;
    return {
      dataMin: domainMin,
      dataMax: domainMax,
      yTicks: flat ? undefined : niceTicks(domainMin, domainMax, 8).ticks,
    };
  }, [chartData, enabledModes]);

  // Compute x-axis ticks based on range
  const { tickDates, tickInterval } = useMemo(() => {
    const allDates = chartData.map((r) => r.fullDate);
    const effectiveRange: DateRange | null = rangeFrom && rangeTo
      ? { from: rangeFrom, to: rangeTo }
      : allDates.length >= 2
        ? { from: allDates[0], to: allDates[allDates.length - 1] }
        : null;
    const days = effectiveRange ? daysInRange(effectiveRange) : allDates.length;
    const ticks = computeTicks(allDates, days);
    const resolution = pickTickResolution(days);
    return { tickDates: ticks, tickInterval: resolution };
  }, [chartData, rangeFrom, rangeTo]);

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-[280px] text-muted-foreground text-body">
        이 기간에 동기화된 데이터가 없습니다
      </div>
    );
  }

  if (chartWidth === 0) {
    return <div ref={chartRef} style={{ width: "100%", height: 280 }} />;
  }

  const minDate = chartData[0].fullDate;
  const maxDate = chartData[chartData.length - 1].fullDate;

  const legendItems: LegendItem[] = ACTIVITY_CATEGORIES
    .filter((cat) => enabledModes.includes(cat.key as ActivitySeries))
    .map((cat) => ({ key: cat.key, label: cat.label, color: cat.hslColor }));

  return (
    <div ref={chartRef} className="space-y-2">
      <LineChart width={chartWidth} height={280} data={chartData} margin={{ top: 4, right: 48, left: -8, bottom: 0 }}>
        <CartesianGrid stroke="hsl(var(--border)/0.45)" vertical={false} />
        <XAxis
          dataKey="fullDate"
          ticks={tickDates}
          tickFormatter={(v: string) => formatTick(v, tickInterval)}
          tick={{ fontSize: "var(--text-caption)", fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
          tickMargin={6}
          minTickGap={36}
          padding={{ left: 0, right: 8 }}
        />
        <YAxis
          domain={[yMin, yMax]}
          ticks={yTicks}
          tick={{ fontSize: "var(--text-caption)", fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
          tickFormatter={formatCompactNumber}
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
            isAnimationActive={newlyAdded.has(mode)}
          />
        ))}
        {Object.entries(syncByDate)
          .filter(([date]) => date >= minDate && date <= maxDate)
          .map(([date, meta]) => (
            <ReferenceLine
              key={`sync-${date}`}
              x={date}
              stroke="hsl(var(--accent))"
              strokeDasharray="4 3"
              strokeWidth={1.5}
              label={<SyncLabel labels={meta.labels} />}
            />
          ))}
        {Object.entries(courseByDate)
          .filter(([date]) => date >= minDate && date <= maxDate)
          .map(([date]) => (
            <ReferenceLine
              key={`course-${date}`}
              x={date}
              stroke="hsl(var(--accent)/0.6)"
              strokeDasharray="2 2"
              strokeWidth={1}
            />
          ))}
      </LineChart>
      {legendItems.length > 0 && (
        <ChartLegend items={legendItems} align="center" />
      )}
    </div>
  );
}
