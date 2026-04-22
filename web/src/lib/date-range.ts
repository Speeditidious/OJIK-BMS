/** Range preset identifiers. */
export type RangePreset = "week" | "month" | "3month" | "year" | "custom";

/** A concrete date range as ISO strings (YYYY-MM-DD). */
export interface DateRange {
  from: string;
  to: string;
}

/** Number of days for each non-custom preset. */
export const PRESET_DAYS: Record<Exclude<RangePreset, "custom">, number> = {
  week: 7,
  month: 30,
  "3month": 90,
  year: 365,
};

/** Human-readable labels for presets. */
export const PRESET_LABELS: Record<RangePreset, string> = {
  week: "1주",
  month: "1달",
  "3month": "3달",
  year: "1년",
  custom: "직접",
};

function toIsoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

/**
 * Compute a DateRange from a non-custom preset.
 * `to` is today; `from` is `days - 1` days before.
 */
export function rangeFromPreset(
  preset: Exclude<RangePreset, "custom">,
  today = new Date(),
): DateRange {
  const days = PRESET_DAYS[preset];
  const from = new Date(today);
  from.setDate(from.getDate() - (days - 1));
  return { from: toIsoDate(from), to: toIsoDate(today) };
}

/**
 * Clamp a DateRange so it does not exceed `maxDays` days.
 * If range exceeds maxDays, `to` is kept and `from` is adjusted.
 */
export function clampRange(range: DateRange, maxDays = 730): DateRange {
  const fromMs = new Date(range.from + "T00:00:00").getTime();
  const toMs = new Date(range.to + "T00:00:00").getTime();
  const days = Math.round((toMs - fromMs) / 86_400_000) + 1;
  if (days <= maxDays) return range;
  const clampedFrom = new Date(toMs - (maxDays - 1) * 86_400_000);
  return { from: toIsoDate(clampedFrom), to: range.to };
}

/** Number of days in a DateRange (inclusive). */
export function daysInRange(range: DateRange): number {
  const fromMs = new Date(range.from + "T00:00:00").getTime();
  const toMs = new Date(range.to + "T00:00:00").getTime();
  return Math.max(1, Math.round((toMs - fromMs) / 86_400_000) + 1);
}
