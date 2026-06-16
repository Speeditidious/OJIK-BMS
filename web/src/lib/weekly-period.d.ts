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
