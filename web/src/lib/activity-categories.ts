/**
 * Canonical activity category definitions, in display order.
 * All UI components (heatmap buttons, bar chart buttons, RecentActivity badges,
 * CalendarDayDetail StatCards, ActivityCalendar dots) reference this array
 * to maintain consistent ordering and colors.
 *
 * Order: score updates → new plays → rating updates → play count
 */

export type ActivityCategory = "updates" | "new_plays" | "rating_updates" | "plays";

export interface ActivityCategoryMeta {
  key: ActivityCategory;
  labelKey: string;
  /** CSS variable reference, e.g. "var(--warning)" */
  cssVar: string;
  /** Full hsl() value, e.g. "hsl(var(--warning))" */
  hslColor: string;
}

export const ACTIVITY_CATEGORIES: ReadonlyArray<ActivityCategoryMeta> = [
  {
    key: "updates",
    labelKey: "format.activity.categories.updates",
    cssVar: "var(--warning)",
    hslColor: "hsl(var(--warning))",
  },
  {
    key: "new_plays",
    labelKey: "format.activity.categories.newPlays",
    cssVar: "var(--primary)",
    hslColor: "hsl(var(--primary))",
  },
  {
    key: "rating_updates",
    labelKey: "format.activity.categories.ratingUpdates",
    cssVar: "var(--chart-rating)",
    hslColor: "hsl(var(--chart-rating))",
  },
  {
    key: "plays",
    labelKey: "format.activity.categories.plays",
    cssVar: "var(--chart-play)",
    hslColor: "hsl(var(--chart-play))",
  },
] as const;
