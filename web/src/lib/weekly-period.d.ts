import type { WeeklyPeriodSummary } from "@/lib/weekly-types";

export interface WeeklyRolloverSettings {
  timezone: string;
  day_of_week: string;
  hour: number;
  minute: number;
}

export interface WeeklyPeriodRange {
  periodStart: string;
  periodEnd: string;
  isCurrent: boolean;
}

export function getWeeklyPeriodForOffset(
  now: Date,
  offset: number,
  rollover: WeeklyRolloverSettings,
): WeeklyPeriodRange;

export function getWeeklyValidOffsetRange(
  periods: WeeklyPeriodSummary[],
  currentPeriodStartIso: string,
): { minOffset: number; maxOffset: 0 } | null;

export function getWeeklyWeekNumber(
  periods: WeeklyPeriodSummary[],
  selectedPeriodStartIso: string,
): number | null;
