/**
 * Determine the tick resolution for an x-axis based on the number of days in the range.
 */
export type TickResolution = "day" | "week" | "month" | "month-year";

export function pickTickResolution(days: number): TickResolution {
  if (days <= 14) return "day";
  if (days <= 60) return "week";
  if (days <= 200) return "month";
  return "month-year";
}

/**
 * Format a date ISO string for a chart x-axis tick.
 * Resolution determines how much detail to show.
 */
export function formatTick(dateIso: string, resolution: TickResolution): string {
  const [year, month, day] = dateIso.split("-").map(Number);
  if (resolution === "day") return `${month}/${day}`;
  if (resolution === "week") return `${month}/${day}`;
  if (resolution === "month") return `${month}월`;
  // month-year
  return `${year} ${month}월`;
}

/**
 * Full date for tooltip display: "YYYY-MM-DD".
 */
export function formatTooltipDate(dateIso: string): string {
  return dateIso;
}

const MAX_TICKS: Record<TickResolution, number> = {
  day: 14,
  week: 10,
  month: 12,
  "month-year": 13,
};

function pickMonthlyCandidates(dates: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const d of dates) {
    const ym = d.slice(0, 7); // YYYY-MM
    if (seen.has(ym)) continue;
    seen.add(ym);
    out.push(d);
  }
  const last = dates[dates.length - 1];
  if (out[out.length - 1] !== last) out.push(last);
  return out;
}

/**
 * Downsample a list of date strings to representative ticks.
 * Always includes the first and last entry.
 * Recharts minTickGap will further reduce visible ticks at runtime.
 */
export function computeTicks(dates: string[], days: number): string[] {
  if (dates.length === 0) return [];
  const resolution = pickTickResolution(days);
  const max = MAX_TICKS[resolution];

  if (resolution === "month" || resolution === "month-year") {
    return pickMonthlyCandidates(dates).slice(0, max);
  }

  // day / week: uniform sampling
  if (dates.length <= max) return dates;
  const step = Math.ceil(dates.length / max);
  const ticks = dates.filter((_, i) => i % step === 0);
  if (ticks[0] !== dates[0]) ticks.unshift(dates[0]);
  if (ticks[ticks.length - 1] !== dates[dates.length - 1])
    ticks.push(dates[dates.length - 1]);
  return Array.from(new Set(ticks));
}
