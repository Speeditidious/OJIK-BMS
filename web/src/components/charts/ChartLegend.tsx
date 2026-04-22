"use client";

import { cn } from "@/lib/utils";

export interface LegendItem {
  key: string;
  label: string;
  color: string; // CSS color string (e.g. "hsl(var(--primary))")
}

interface ChartLegendProps {
  items: LegendItem[];
  className?: string;
  /** Alignment of legend items. Defaults to "start". */
  align?: "start" | "center" | "end";
}

/**
 * Simple horizontal chart legend with colored dot + label.
 * Accessibility: role="list" on wrapper, role="listitem" per entry.
 */
export function ChartLegend({ items, className, align = "start" }: ChartLegendProps) {
  return (
    <div
      role="list"
      className={cn(
        "flex flex-wrap items-center gap-3 text-caption text-muted-foreground",
        align === "center" && "justify-center",
        align === "end" && "justify-end",
        className,
      )}
    >
      {items.map((item) => (
        <div key={item.key} role="listitem" className="flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full flex-shrink-0"
            style={{ backgroundColor: item.color }}
            aria-hidden="true"
          />
          <span>{item.label}</span>
        </div>
      ))}
    </div>
  );
}
