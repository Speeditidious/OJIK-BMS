"use client";

import { useMemo, useState, memo, useRef, useCallback } from "react";
import {
  Bar,
  BarChart,
  ReferenceLine,
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
import { useChartWidth } from "@/hooks/use-chart-size";

// All internal clear types. Bars are declared highest → lowest so the
// highest tier (MAX/PERFECT/FC) renders on the left in stacked bars.
export const ALL_CLEAR_TYPES = [9, 8, 7, 6, 5, 4, 3, 2, 1, 0] as const;

interface TableClearHistogramProps {
  levels: TableClearLevel[];
  clientType?: string;
  tableSymbol?: string;
  onSelect?: (level: string, clearType: number) => void;
  onLevelSelect?: (level: string) => void;
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

const CustomTooltip = memo(function CustomTooltip({ active, payload, label, tableSymbol, clientType, activeEntry, labelMap }: CustomTooltipProps) {
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
        // exclude zero-count entries so the tooltip stays compact
        const rawCount = rowData?.[`raw_ct_${ct}`] ?? 0;
        return rawCount > 0;
      }).map((ct) => {
        const rawCount = rowData?.[`raw_ct_${ct}`] ?? 0;
        const ctLabel = labelMap[ct] ?? String(ct);
        const ownPct = total > 0 ? (rawCount / total) * 100 : 0;
        let cumRaw = rawCount;
        for (const o of ALL_CLEAR_TYPES) {
          if (o > ct) cumRaw += rowData?.[`raw_ct_${o}`] ?? 0;
        }
        const cumPct = total > 0 ? (cumRaw / total) * 100 : 0;
        const isActive = activeEntry?.ct === ct;
        return (
          <div
            key={ct}
            style={{
              color: isActive ? CLEAR_TYPE_COLORS[ct] : "hsl(var(--muted-foreground))",
              fontWeight: isActive ? 700 : 400,
              transition: "color 0.15s, font-weight 0.15s",
              display: "flex",
              gap: "4px",
              alignItems: "baseline",
            }}
          >
            <span style={{ width: 56 }}>{ctLabel}</span>
            <span style={{ width: 20, color: isActive ? CLEAR_TYPE_COLORS[ct] : "hsl(var(--foreground))", fontWeight: isActive ? 700 : 500 }}>
              {rawCount.toLocaleString()}
            </span>
            <span style={{ width: 46, color: isActive ? CLEAR_TYPE_COLORS[ct] : "hsl(var(--foreground))", fontWeight: isActive ? 700 : 400 }}>
              ({ownPct.toFixed(1)}%)
            </span>
            <span style={{ width: 64, fontSize: 10, color: isActive ? CLEAR_TYPE_COLORS[ct] : "hsl(var(--muted-foreground))" }}>
              누적 {cumPct.toFixed(1)}%
            </span>
          </div>
        );
      })}
    </div>
  );
});

// Step 4: YAxisTick — useState removed; hover effect via CSS class
const YAxisTick = memo(function YAxisTick({
  x,
  y,
  payload,
  tableSymbol,
  onLevelSelect,
}: {
  x?: number;
  y?: number;
  payload?: { value: unknown };
  tableSymbol?: string;
  onLevelSelect?: (level: string) => void;
}) {
  const val = String(payload?.value ?? "");
  const label = val.startsWith("LEVEL ") ? val.slice(6) : val;
  const displayLabel = tableSymbol ? `${tableSymbol}${label}` : label;
  const isClickable = !!onLevelSelect;
  return (
    <g transform={`translate(${x},${y})`}>
      <text
        x={0}
        y={0}
        dy={4}
        textAnchor="end"
        fontSize={11}
        fill="hsl(var(--foreground))"
        className={isClickable ? "hist-yaxis-tick" : undefined}
        style={{ cursor: isClickable ? "pointer" : "default" }}
        onClick={isClickable ? () => onLevelSelect(val) : undefined}
      >
        {displayLabel}
      </text>
    </g>
  );
});

export function TableClearHistogram({ levels, clientType, tableSymbol, onSelect, onLevelSelect }: TableClearHistogramProps) {
  // All hooks at top — no early returns before this block
  const [activeEntry, setActiveEntry] = useState<{ level: string; ct: number } | null>(null);
  const highlightStyleRef = useRef<HTMLStyleElement>(null);
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
      levels.map((l) => {
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

  const barHeight = useMemo(
    () => Math.max(12, Math.min(26, 360 / Math.max(1, levels.length))),
    [levels.length]
  );

  const chartHeight = useMemo(
    () => levels.length * (barHeight + 6) + 52,
    [levels.length, barHeight]
  );

  // Step 5: Direct DOM manipulation for bar highlight — zero React re-renders
  const updateBarHighlight = useCallback((entry: { level: string; ct: number } | null) => {
    const el = highlightStyleRef.current;
    if (!el) return;

    if (!entry) {
      el.textContent = "";
      return;
    }

    // CSS.escape required: BMS levels may contain ★, +, spaces, etc.
    const lvl = CSS.escape(entry.level);
    const ct = entry.ct;

    el.textContent = `
      .hist-wrapper .hist-bar[data-level="${lvl}"]:not([data-ct="${ct}"]) { opacity: 0.5 !important; }
      .hist-wrapper .hist-bar[data-ct="${ct}"][data-level="${lvl}"] { opacity: 1 !important; transform: scaleY(1.4); }
    `;
  }, []);

  // Step 2: bar shapes — CSS transition removed; data-ct/data-level/className added
  // CRITICAL: NO activeEntry dependency — prevents shape recreation on every hover,
  // which would cause Recharts to re-render all 300+ bars each time.
  const barShapes = useMemo(() => {
    const shapes: Record<number, (props: any) => JSX.Element> = {};
    for (const ct of ALL_CLEAR_TYPES) {
      shapes[ct] = (barProps: any) => {
        const { x, y, width, height } = barProps;
        if (!height || height <= 0) return <rect width={0} height={0} />;
        const level = barProps.payload?.level ?? "";
        return (
          <rect
            x={x}
            y={y}
            width={width}
            height={height}
            fill={CLEAR_TYPE_COLORS[ct] ?? "hsl(var(--muted))"}
            opacity={0.9}
            className="hist-bar"
            data-ct={ct}
            data-level={level}
            style={{ cursor: onSelect ? "pointer" : "default" }}
          />
        );
      };
    }
    return shapes;
  }, [onSelect]);

  if (levels.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
        난이도표 데이터가 없습니다
      </div>
    );
  }

  // Step 1: width=0 on first render → placeholder div for ResizeObserver to measure
  if (chartWidth === 0) {
    return <div ref={chartRef} style={{ width: "100%", height: chartHeight }} />;
  }

  return (
    <div ref={chartRef} className="hist-wrapper">
      {/* Step 5: empty <style> tag — JS writes CSS rules directly on hover */}
      <style ref={highlightStyleRef} />
      <BarChart
        width={chartWidth}
        height={chartHeight}
        data={chartData}
        layout="vertical"
        margin={{ top: 4, right: 12, left: 12, bottom: 4 }}
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
          tick={<YAxisTick tableSymbol={tableSymbol} onLevelSelect={onLevelSelect} />}
          tickLine={false}
          axisLine={false}
          interval={0}
          width={tableSymbol ? Math.max(88, tableSymbol.length * 12 + 48) : 80}
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
            shape={barShapes[ct]}
            onClick={(data) => onSelect?.(data.level as string, ct)}
            onMouseEnter={(data) => {
              const entry = { level: data.level as string, ct };
              setActiveEntry(entry);        // tooltip용 (React 상태)
              updateBarHighlight(entry);    // bar 시각효과 (DOM 직접 조작)
            }}
            onMouseLeave={() => {
              setActiveEntry(null);
              updateBarHighlight(null);
            }}
          />
        ))}
      </BarChart>
      <ClearTypeLegend clientType={clientType} className="mb-8" />
    </div>
  );
}

// Legend items per client type
const COMBINED_ITEMS = [9, 8, 7, 6, 5, 4, 3, 2, 1, 0] as const;
const LR2_ITEMS = [9, 8, 7, 5, 4, 3, 1, 0] as const;
const BEATORAJA_ITEMS = [9, 8, 7, 6, 5, 4, 3, 2, 1, 0] as const;

interface ClearTypeLegendProps {
  clientType?: string;
  className?: string;
}

export function ClearTypeLegend({ clientType, className }: ClearTypeLegendProps) {
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
    <div className={`flex flex-wrap justify-center gap-x-4 gap-y-1 mt-1 ${className ?? ""}`}>
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
