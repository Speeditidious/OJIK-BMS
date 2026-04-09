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

interface ActivityBarChartProps {
  data: ActivityDay[];
  firstSyncDates?: { lr2?: string; beatoraja?: string };
  clientType?: ClientTypeFilter;
  courseData?: CourseActivityItem[];
  viewMode?: "updates" | "plays" | "new_plays";
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

// Custom SVG label that renders multiple lines of text
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
          fontSize='var(--text-caption)'
          textAnchor="start"
        >
          {label}
        </text>
      ))}
    </g>
  );
}

function ChartTooltip({ active, payload, viewMode }: { active?: boolean; payload?: any[]; viewMode?: "updates" | "plays" | "new_plays" }) {
  if (!active || !payload?.length) return null;
  const { fullDate, updates, new_plays, plays, syncLabels, hideSyncCount, courseLabels } = payload[0].payload as {
    fullDate: string;
    updates: number;
    new_plays: number;
    plays: number;
    syncLabels?: string[];
    hideSyncCount?: boolean;
    courseLabels?: string[];
  };
  const hasAnySyncLabel = syncLabels?.length;
  const showCounts = !hideSyncCount || courseLabels?.length;
  return (
    <div
      style={{
        backgroundColor: "hsl(var(--card))",
        border: "1px solid hsl(var(--border))",
        borderRadius: "6px",
        fontSize: 'var(--text-label)',
        color: "hsl(var(--foreground))",
        padding: "8px 10px",
      }}
    >
      <p style={{ marginBottom: (hasAnySyncLabel || courseLabels?.length) ? 4 : 0 }}>{fullDate}</p>
      {hasAnySyncLabel && syncLabels!.map((l) => (
        <p key={l} style={{ color: "hsl(var(--accent))", margin: 0 }}>
          {l}
        </p>
      ))}
      {courseLabels?.map((l) => (
        <p key={l} style={{ color: "hsl(var(--accent))", margin: 0 }}>
          {l}
        </p>
      ))}
      {showCounts && (updates > 0 || new_plays > 0 || plays > 0) && (
        <div style={{ marginTop: (hasAnySyncLabel || courseLabels?.length) ? 4 : 0 }}>
          <p style={{ margin: 0, color: "hsl(var(--primary))", fontWeight: viewMode === "updates" ? 600 : 400 }}>
            갱신 기록: {updates}
          </p>
          <p style={{ margin: 0, color: "hsl(var(--chart-new-play))", fontWeight: viewMode === "new_plays" ? 600 : 400 }}>
            신규 기록: {new_plays}
          </p>
          <p style={{ margin: 0, color: "hsl(var(--chart-play))", fontWeight: viewMode === "plays" ? 600 : 400 }}>
            플레이: {plays}
          </p>
        </div>
      )}
    </div>
  );
}

export function ActivityBarChart({ data, firstSyncDates, clientType, courseData, viewMode = "updates" }: ActivityBarChartProps) {
  const [chartRef, chartWidth] = useChartWidth(150);
  // Build per-date sync metadata.
  // hideCount=true for LR2-only dates: LR2 score.db has no per-play date, so all
  // records land on the sync day — the count would be misleading.
  const syncByDate = useMemo(() => {
    const map: Record<string, { labels: string[]; hideCount: boolean }> = {};
    if (!firstSyncDates) return map;
    if (clientType !== "beatoraja" && firstSyncDates.lr2) {
      const d = firstSyncDates.lr2;
      const prev = map[d] ?? { labels: [], hideCount: true };
      prev.labels.push("LR2 첫 동기화");
      map[d] = prev;
    }
    if (clientType !== "lr2" && firstSyncDates.beatoraja) {
      const d = firstSyncDates.beatoraja;
      const prev = map[d] ?? { labels: [], hideCount: true };
      prev.labels.push("Beatoraja 첫 동기화");
      prev.hideCount = false; // Beatoraja has real play dates → show count
      map[d] = prev;
    }
    return map;
  }, [firstSyncDates, clientType]);

  const courseByDate = useMemo(() => {
    if (!courseData?.length) return {} as Record<string, string[]>;
    const map: Record<string, string[]> = {};
    for (const c of courseData) {
      if (!c.date) continue;
      const label = c.course_name
        ? (c.dan_title ? `[${c.dan_title}] ` : "") + c.course_name
        : `코스 (${c.course_hash.slice(0, 6)}…)`;
      (map[c.date] ??= []).push(label);
    }
    return map;
  }, [courseData]);

  const chartData = useMemo(() => {
    const seenDates = new Set(data.map((d) => d.date));
    const injected = [...data];
    // When data exists, only inject sync dates at or after the natural data range start to
    // avoid stretching the X-axis back to old LR2 sync dates in "all" mode.
    // Sync dates after rangeMax are allowed — they add one point to the right edge
    // (e.g. user synced today but last play was yesterday).
    // When data is empty, inject all sync dates so the reference lines still show.
    const rangeMin = data.length > 0 ? data[0].date : null;
    for (const date of Object.keys(syncByDate)) {
      if (!seenDates.has(date) && (rangeMin === null || date >= rangeMin)) {
        injected.push({ date, updates: 0, new_plays: 0, plays: 0 });
        seenDates.add(date);
      }
    }
    for (const date of Object.keys(courseByDate)) {
      if (!seenDates.has(date) && (rangeMin === null || date >= rangeMin)) {
        injected.push({ date, updates: 0, new_plays: 0, plays: 0 });
        seenDates.add(date);
      }
    }
    injected.sort((a, b) => a.date.localeCompare(b.date));
    return injected.map((d) => ({
      date: formatDate(d.date),
      fullDate: d.date,
      updates: d.updates,
      new_plays: d.new_plays ?? 0,
      plays: d.plays,
      syncLabels: syncByDate[d.date]?.labels,
      hideSyncCount: syncByDate[d.date]?.hideCount ?? false,
      courseLabels: courseByDate[d.date],
    }));
  }, [data, syncByDate, courseByDate]);

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
          tick={{ fontSize: 'var(--text-caption)', fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 'var(--text-caption)', fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
        />
        <Tooltip
          content={<ChartTooltip viewMode={viewMode} />}
          cursor={{ stroke: "hsl(var(--accent))", strokeWidth: 1 }}
        />
        <Line
          type="monotone"
          dataKey="plays"
          stroke="hsl(var(--chart-play))"
          strokeWidth={viewMode === "plays" ? 2 : 1.5}
          strokeDasharray={viewMode === "plays" ? undefined : "3 2"}
          strokeOpacity={viewMode === "plays" ? 1 : 0.5}
          dot={false}
          activeDot={{ r: viewMode === "plays" ? 3 : 2, fill: "hsl(var(--chart-play))" }}
        />
        <Line
          type="monotone"
          dataKey="new_plays"
          stroke="hsl(var(--chart-new-play))"
          strokeWidth={viewMode === "new_plays" ? 2 : 1.5}
          strokeDasharray={viewMode === "new_plays" ? undefined : "3 2"}
          strokeOpacity={viewMode === "new_plays" ? 1 : 0.8}
          dot={false}
          activeDot={{ r: viewMode === "new_plays" ? 3 : 2, fill: "hsl(var(--chart-new-play))" }}
        />
        <Line
          type="monotone"
          dataKey="updates"
          stroke="hsl(var(--primary))"
          strokeWidth={viewMode === "updates" ? 2 : 1.5}
          strokeDasharray={viewMode === "updates" ? undefined : "3 2"}
          strokeOpacity={viewMode === "updates" ? 1 : 0.5}
          dot={false}
          activeDot={{ r: viewMode === "updates" ? 3 : 2, fill: "hsl(var(--primary))" }}
        />
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
                  ? { value: meta.labels[0], position: "insideTopRight", fontSize: 'var(--text-caption)', fill: "hsl(var(--accent))" }
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
