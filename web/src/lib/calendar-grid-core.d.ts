export interface CalendarCell {
  dateStr: string;
  day: number;
  currentMonth: boolean;
}

export function pad2(n: number): string;
export function toDateString(year: number, month: number, day: number): string;
export function shiftMonth(year: number, month: number, delta: number): { year: number; month: number };
export function buildMonthCells(year: number, month: number): CalendarCell[];
export function getMonthRange(year: number, month: number): { from: string; to: string };
export function isMonthAfter(year: number, month: number, dateStr: string): boolean;
export function previewRange(
  from: string | null,
  to: string | null,
  hover: string | null,
): { from: string; to: string } | null;
