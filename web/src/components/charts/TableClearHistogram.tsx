"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { TableClearLevel } from "@/hooks/use-analysis";
import {
  CLEAR_TYPE_COLORS,
  CLEAR_TYPE_LABELS,
  LR2_CLEAR_TYPE_LABELS,
  BEATORAJA_CLEAR_TYPE_LABELS,
} from "@/components/charts/ClearDistributionChart";

// All internal clear types. Bars are declared highest → lowest so the
// highest tier (MAX/PERFECT/FC) renders on the left in stacked bars.
export const ALL_CLEAR_TYPES = [9, 8, 7, 6, 5, 4, 3, 2, 1, 0] as const;

interface TableClearHistogramProps {
  levels: TableClearLevel[];
  clientType?: string;
  tableSymbol?: string;
  onSelect?: (level: string, clearType: number) => void;
}

const cardStyles: React.CSSProperties = {
  backgroundColor: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: "6px",
  padding: "8px 12px",
  fontSize: 11,
};

interface CustomTooltipProps {
  active?: boolean;
  payload?: any[];
  label?: string;
  tableSymbol?: string;
  clientType?: string;
  activeEntry?: { level: string; ct: number } | null;
  labelMap: Record<number, string>;
}

function CustomTooltip({ active, payload, label, tableSymbol, clientType, activeEntry, labelMap }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const rowData = payload[0]?.payload as Record<string, number>;
  const total = rowData?._total ?? 0;

  return (
    <div style={cardStyles}>
      {(() => {
        const displayLevel =
          String(label).startsWith("LEVEL ") ? String(label).slice(6) : String(label);
        return (
          <div className="font-semibold text-foreground mb-1">
            {tableSymbol ? `${tableSymbol}${displayLevel}` : displayLevel}
          </div>
        );
      })()}
      {ALL_CLEAR_TYPES.filter((ct) => {
        // LR2 has no ASSIST(2) or EXHARD(6)
        if (clientType === "lr2" && (ct === 2 || ct === 6)) return false;
        return true;
      }).map((ct) => {
        const rawCount = rowData?.[`raw_ct_${ct}`] ?? 0;
        const ctLabel = labelMap[ct] ?? String(ct);
        let cumRaw = rawCount;
        for (const o of ALL_CLEAR_TYPES) {
          if (o > ct) cumRaw += rowData?.[`raw_ct_${o}`] ?? 0;
        }
        const pct = total > 0 ? (cumRaw / total) * 100 : 0;
        const isActive = activeEntry?.ct === ct;
        return (
          <div
            key={ct}
            style={{
              color: isActive ? CLEAR_TYPE_COLORS[ct] : "hsl(var(--muted-foreground))",
              fontWeight: isActive ? 700 : 400,
              transition: "color 0.15s, font-weight 0.15s",
              display: "flex",
              gap: "6px",
            }}
          >
            <span>{ctLabel}</span>
            <span>:</span>
            <span>{rawCount}</span>
            <span>({pct.toFixed(1)}%)</span>
          </div>
        );
      })}
    </div>
  );
}

export function TableClearHistogram({ levels, clientType, tableSymbol, onSelect }: TableClearHistogramProps) {
  const [activeEntry, setActiveEntry] = useState<{ level: string; ct: number } | null>(null);

  const labelMap =
    clientType === "lr2"
      ? LR2_CLEAR_TYPE_LABELS
      : clientType === "beatoraja"
      ? BEATORAJA_CLEAR_TYPE_LABELS
      : CLEAR_TYPE_LABELS;

  const chartData = useMemo(
    () =>
      levels.map((l) => {
        // Compute raw counts and total for percentage conversion
        const rawCounts: Record<string, number> = {};
        let total = 0;
        for (const ct of ALL_CLEAR_TYPES) {
          const raw = l.counts[String(ct)] ?? 0;
          rawCounts[`raw_${ct}`] = raw;
          total += raw;
        }

        const row: Record<string, string | number> = { level: l.level, _total: total };
        for (const ct of ALL_CLEAR_TYPES) {
          row[`ct_${ct}`] = total > 0 ? (rawCounts[`raw_${ct}`] / total) * 100 : 0;
          row[`raw_ct_${ct}`] = rawCounts[`raw_${ct}`];
        }
        return row;
      }),
    [levels]
  );

  if (levels.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
        난이도표 데이터가 없습니다
      </div>
    );
  }

  const barHeight = Math.max(12, Math.min(26, 360 / levels.length));
  const chartHeight = levels.length * (barHeight + 6) + 52;

  // Custom shape factory for hover animation
  function makeShape(ct: number) {
    function BarShape(barProps: any) {
      const { x, y, width, height, payload } = barProps;
      if (!height || height <= 0) return <rect width={0} height={0} />;
      const level = payload?.level as string;
      const isThis = activeEntry?.ct === ct && activeEntry?.level === level;
      const sameRowOther = activeEntry?.level === level && activeEntry?.ct !== ct;
      return (
        <rect
          x={x}
          y={y}
          width={width}
          height={height}
          fill={CLEAR_TYPE_COLORS[ct] ?? "hsl(var(--muted))"}
          style={{
            transformBox: "fill-box" as any,
            transformOrigin: "center",
            transform: isThis ? "scaleY(1.2)" : "scaleY(1)",
            transition: "transform 0.15s ease, opacity 0.15s ease",
            opacity: sameRowOther ? 0.4 : 0.9,
            cursor: onSelect ? "pointer" : "default",
          }}
        />
      );
    }
    return BarShape;
  }

  return (
    <ResponsiveContainer width="100%" height={chartHeight}>
      <BarChart
        data={chartData}
        layout="vertical"
        margin={{ top: 4, right: 12, left: 12, bottom: 20 }}
        barCategoryGap="12%"
      >
        <XAxis
          type="number"
          domain={[0, 100]}
          ticks={[0, 25, 50, 75, 100]}
          tickFormatter={(v) => `${v}%`}
          tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          type="category"
          dataKey="level"
          tick={{ fontSize: 11, fill: "hsl(var(--foreground))" }}
          tickLine={false}
          axisLine={false}
          interval={0}
          width={tableSymbol ? Math.max(88, tableSymbol.length * 12 + 48) : 80}
          tickFormatter={(val) => {
            const label = String(val).startsWith("LEVEL ") ? String(val).slice(6) : String(val);
            return tableSymbol ? `${tableSymbol}${label}` : label;
          }}
        />
        <Tooltip
          content={<CustomTooltip tableSymbol={tableSymbol} clientType={clientType} activeEntry={activeEntry} labelMap={labelMap} />}
          cursor={{ fill: "hsl(var(--accent)/0.08)" }}
        />
        {[25, 50, 75].map((v) => (
          <ReferenceLine
            key={v}
            x={v}
            stroke="hsl(var(--muted-foreground))"
            strokeOpacity={0.45}
            strokeWidth={1}
            strokeDasharray="3 3"
          />
        ))}
        {ALL_CLEAR_TYPES.map((ct) => (
          <Bar
            key={ct}
            dataKey={`ct_${ct}`}
            stackId="stack"
            maxBarSize={barHeight}
            shape={makeShape(ct)}
            onClick={(data) => onSelect?.(data.level as string, ct)}
            onMouseEnter={(data) => setActiveEntry({ level: data.level as string, ct })}
            onMouseLeave={() => setActiveEntry(null)}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

// Legend items per client type
const COMBINED_ITEMS = [9, 8, 7, 6, 5, 4, 3, 2, 1, 0] as const;
const LR2_ITEMS = [9, 8, 7, 5, 4, 3, 1, 0] as const;
const BEATORAJA_ITEMS = [9, 8, 7, 6, 5, 4, 3, 2, 1, 0] as const;

interface ClearTypeLegendProps {
  clientType?: string;
}

export function ClearTypeLegend({ clientType }: ClearTypeLegendProps) {
  const labelMap =
    clientType === "lr2"
      ? LR2_CLEAR_TYPE_LABELS
      : clientType === "beatoraja"
      ? BEATORAJA_CLEAR_TYPE_LABELS
      : CLEAR_TYPE_LABELS;

  const items =
    clientType === "lr2"
      ? LR2_ITEMS
      : clientType === "beatoraja"
      ? BEATORAJA_ITEMS
      : COMBINED_ITEMS;

  return (
    <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-1">
      {items.map((ct) => (
        <div key={ct} className="flex items-center gap-1.5">
          <div
            className="w-3 h-3 rounded-sm flex-shrink-0"
            style={{ background: CLEAR_TYPE_COLORS[ct] }}
          />
          <span className="text-[11px] text-muted-foreground">{labelMap[ct] ?? String(ct)}</span>
        </div>
      ))}
    </div>
  );
}
