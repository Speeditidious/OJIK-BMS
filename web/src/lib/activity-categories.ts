/**
 * Canonical activity category definitions, in display order.
 * All UI components (heatmap buttons, bar chart buttons, RecentActivity badges,
 * CalendarDayDetail StatCards, ActivityCalendar dots) reference this array
 * to maintain consistent ordering and colors.
 *
 * Order: 갱신 기록 → 신규 기록 → 레이팅 갱신 → 플레이 횟수
 */

export type ActivityCategory = "updates" | "new_plays" | "rating_updates" | "plays";

export interface ActivityCategoryMeta {
  key: ActivityCategory;
  label: string;
  /** CSS variable reference, e.g. "var(--warning)" */
  cssVar: string;
  /** Full hsl() value, e.g. "hsl(var(--warning))" */
  hslColor: string;
}

export const ACTIVITY_CATEGORIES: ReadonlyArray<ActivityCategoryMeta> = [
  {
    key: "updates",
    label: "갱신 기록",
    cssVar: "var(--warning)",
    hslColor: "hsl(var(--warning))",
  },
  {
    key: "new_plays",
    label: "신규 기록",
    cssVar: "var(--primary)",
    hslColor: "hsl(var(--primary))",
  },
  {
    key: "rating_updates",
    label: "레이팅 갱신",
    cssVar: "var(--chart-rating)",
    hslColor: "hsl(var(--chart-rating))",
  },
  {
    key: "plays",
    label: "플레이 횟수",
    cssVar: "var(--chart-play)",
    hslColor: "hsl(var(--chart-play))",
  },
] as const;
