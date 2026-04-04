"use client";

import { useMemo, useCallback } from "react";
import {
  Bar,
  BarChart,
  Cell,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { GradeDistributionItem } from "@/hooks/use-analysis";
import { useChartWidth } from "@/hooks/use-chart-size";

// Internal clear type system (numeric order = quality order):
// 0=NO PLAY, 1=FAILED, 2=ASSIST, 3=EASY, 4=NORMAL, 5=HARD, 6=EXHARD, 7=FC, 8=PERFECT, 9=MAX
// LR2 uses: 0, 1, 3, 4, 5, 7 (no ASSIST/EXHARD/PERFECT/MAX)
// Beatoraja uses: 0-9

export const CLEAR_TYPE_LABELS: Record<number, string> = {
  0: "NO PLAY", 1: "FAILED", 2: "ASSIST", 3: "EASY", 4: "NORMAL",
  5: "HARD", 6: "EXHARD", 7: "FC", 8: "PERFECT", 9: "MAX",
};

// Per-client labels when client_type is known
export const LR2_CLEAR_TYPE_LABELS: Record<number, string> = {
  0: "NO PLAY", 1: "FAILED", 3: "EASY", 4: "NORMAL", 5: "HARD", 7: "FC",
  8: "PERFECT", 9: "MAX",
};

export const BEATORAJA_CLEAR_TYPE_LABELS: Record<number, string> = {
  0: "NO PLAY", 1: "FAILED", 2: "ASSIST", 3: "EASY", 4: "NORMAL",
  5: "HARD", 6: "EXHARD", 7: "FC", 8: "PERFECT", 9: "MAX",
};

// BMS convention hues, pastel-ized via CSS variables defined in globals.css
export const CLEAR_TYPE_COLORS: Record<number, string> = {
  0: "hsl(var(--clear-no-play))",
  1: "hsl(var(--clear-failed))",
  2: "hsl(var(--clear-assist))",
  3: "hsl(var(--clear-easy))",
  4: "hsl(var(--clear-normal))",
  5: "hsl(var(--clear-hard))",
  6: "hsl(var(--clear-exhard))",
  7: "hsl(var(--clear-fc))",
  8: "hsl(var(--clear-perfect))",
  9: "hsl(var(--clear-max))",
};

interface ClearDistributionChartProps {
  data: GradeDistributionItem[];
  clientType?: string; // "lr2" | "beatoraja" — used to resolve ambiguous labels
}

export function ClearDistributionChart({ data, clientType }: ClearDistributionChartProps) {
  // All hooks at top before any early returns
  const [chartRef, chartWidth] = useChartWidth(150);

  const labelMap = useMemo(
    () =>
      clientType === "lr2"
        ? LR2_CLEAR_TYPE_LABELS
        : clientType === "beatoraja"
        ? BEATORAJA_CLEAR_TYPE_LABELS
        : CLEAR_TYPE_LABELS,
    [clientType]
  );

  const chartData = useMemo(
    () =>
      data
        .filter((d) => d.clear_type !== null)
        .sort((a, b) => (b.clear_type ?? 0) - (a.clear_type ?? 0))
        .map((d) => ({
          label: labelMap[d.clear_type ?? 0] ?? String(d.clear_type),
          count: d.count,
          type: d.clear_type ?? 0,
        })),
    [data, labelMap]
  );

  const totalCount = useMemo(
    () => chartData.reduce((acc, d) => acc + d.count, 0),
    [chartData]
  );

  const chartHeight = useMemo(
    () => chartData.length * 24,
    [chartData.length]
  );

  const renderTooltip = useCallback(
    ({ active, payload }: any) => {
      if (!active || !payload?.length) return null;
      const entry = payload[0].payload;
      const ct = entry.type as number;
      const value = entry.count as number;
      const cumRaw = chartData.filter((d) => d.type >= ct).reduce((s, d) => s + d.count, 0);
      const pct = totalCount > 0 ? (cumRaw / totalCount) * 100 : 0;
      return (
        <div style={{
          backgroundColor: "hsl(var(--card))",
          border: "1px solid hsl(var(--border))",
          borderRadius: "6px",
          padding: "8px 12px",
          fontSize: "var(--text-label)",
          color: "hsl(var(--foreground))",
          whiteSpace: "nowrap",
          width: "max-content",
        }}>
          <p style={{ fontWeight: 600, marginBottom: 2 }}>{labelMap[ct]}</p>
          <p>{value.toLocaleString()} ({pct.toFixed(1)}%)</p>
        </div>
      );
    },
    [chartData, totalCount, labelMap]
  );

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground text-body">
        스코어 데이터가 없습니다
      </div>
    );
  }

  if (chartWidth === 0) {
    return <div ref={chartRef} style={{ width: "100%", height: chartHeight }} />;
  }

  return (
    <div ref={chartRef}>
      <BarChart
        width={chartWidth}
        height={chartHeight}
        data={chartData}
        layout="vertical"
        barCategoryGap="12%"
        margin={{ top: 0, right: 8, left: 8, bottom: 0 }}
      >
        <XAxis
          type="number"
          tick={{ fontSize: 'var(--text-caption)', fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
        />
        <YAxis
          type="category"
          dataKey="label"
          tick={{ fontSize: 'var(--text-caption)', fill: "hsl(var(--foreground))" }}
          tickLine={false}
          axisLine={false}
          width={56}
        />
        <Tooltip
          content={renderTooltip}
          cursor={{ fill: "hsl(var(--accent)/0.1)" }}
        />
        <Bar dataKey="count" radius={[0, 3, 3, 0]} barSize={16}>
          {chartData.map((entry) => (
            <Cell key={entry.type} fill={CLEAR_TYPE_COLORS[entry.type]} />
          ))}
        </Bar>
      </BarChart>
    </div>
  );
}
