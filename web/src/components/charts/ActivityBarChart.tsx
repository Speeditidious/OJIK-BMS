"use client";

import { useMemo } from "react";
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ActivityDay, ClientTypeFilter, CourseActivityItem } from "@/hooks/use-analysis";

interface ActivityBarChartProps {
  data: ActivityDay[];
  firstSyncDates?: { lr2?: string; beatoraja?: string };
  clientType?: ClientTypeFilter;
  courseData?: CourseActivityItem[];
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
          fontSize={10}
          textAnchor="start"
        >
          {label}
        </text>
      ))}
    </g>
  );
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: any[] }) {
  if (!active || !payload?.length) return null;
  const { fullDate, updates, syncLabels, hideSyncCount, courseLabels } = payload[0].payload as {
    fullDate: string;
    updates: number;
    syncLabels?: string[];
    hideSyncCount?: boolean;
    courseLabels?: string[];
  };
  const hasAnySyncLabel = syncLabels?.length;
  return (
    <div
      style={{
        backgroundColor: "hsl(var(--card))",
        border: "1px solid hsl(var(--border))",
        borderRadius: "6px",
        fontSize: 12,
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
      {updates > 0 && (!hideSyncCount || courseLabels?.length) && (
        <p style={{ margin: 0, marginTop: (hasAnySyncLabel || courseLabels?.length) ? 4 : 0, color: "hsl(var(--foreground))" }}>
          기록 갱신: {updates}
        </p>
      )}
      {updates === 0 && !hasAnySyncLabel && !courseLabels?.length && (
        <p style={{ margin: 0 }}>기록 갱신: {updates}</p>
      )}
    </div>
  );
}

export function ActivityBarChart({ data, firstSyncDates, clientType, courseData }: ActivityBarChartProps) {
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
      const label = (c.is_first_clear ? "★ " : "") + `코스 클리어 (${c.course_hash.slice(0, 6)}…)`;
      (map[c.date] ??= []).push(label);
    }
    return map;
  }, [courseData]);

  const chartData = useMemo(() => {
    const rawDates = new Set(data.map((d) => d.date));
    const injected = [...data];
    // When data exists, only inject sync dates at or after the natural data range start to
    // avoid stretching the X-axis back to old LR2 sync dates in "all" mode.
    // Sync dates after rangeMax are allowed — they add one point to the right edge
    // (e.g. user synced today but last play was yesterday).
    // When data is empty, inject all sync dates so the reference lines still show.
    const rangeMin = data.length > 0 ? data[0].date : null;
    for (const date of Object.keys(syncByDate)) {
      if (!rawDates.has(date) && (rangeMin === null || date >= rangeMin)) {
        injected.push({ date, updates: 0 });
      }
    }
    for (const date of Object.keys(courseByDate)) {
      if (!rawDates.has(date) && (rangeMin === null || date >= rangeMin)) {
        injected.push({ date, updates: 0 });
      }
    }
    injected.sort((a, b) => a.date.localeCompare(b.date));
    return injected.map((d) => ({
      date: formatDate(d.date),
      fullDate: d.date,
      updates: d.updates,
      syncLabels: syncByDate[d.date]?.labels,
      hideSyncCount: syncByDate[d.date]?.hideCount ?? false,
      courseLabels: courseByDate[d.date],
    }));
  }, [data, syncByDate, courseByDate]);

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
        이 기간에 동기화된 데이터가 없습니다
      </div>
    );
  }

  const minDate = chartData[0].fullDate;
  const maxDate = chartData[chartData.length - 1].fullDate;

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
        />
        <Tooltip
          content={<ChartTooltip />}
          cursor={{ stroke: "hsl(var(--accent))", strokeWidth: 1 }}
        />
        <Line
          type="monotone"
          dataKey="updates"
          stroke="hsl(var(--primary))"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 3, fill: "hsl(var(--primary))" }}
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
                  ? { value: meta.labels[0], position: "insideTopRight", fontSize: 10, fill: "hsl(var(--accent))" }
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
    </ResponsiveContainer>
  );
}
