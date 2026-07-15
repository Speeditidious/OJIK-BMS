/**
 * Shared types for the goal-setup ("quest") feature (Tasks 12-14, not yet
 * built). Split into its own file because `RatingCalculatorDialog.tsx`
 * (Task 3) already needs to produce a `GoalDraft` via its `onSetGoal` prop,
 * ahead of the goal-setup UI that will consume it.
 */

/**
 * A draft goal condition captured from the rating calculator's adjusted
 * clear/rank/BP/rate controls, handed to the (future) goal-setup dialog via
 * `RatingCalculatorDialog`'s `onSetGoal` prop.
 */
export interface GoalDraft {
  tableSlug: string;
  fumen: {
    sha256: string | null;
    md5: string | null;
    level: string;
    title: string;
    artist: string | null;
    symbol?: string;
  };
  clientType: string;
  clearType: number | null;
  rank: string | null;
  minBp: number | null;
  rate: number | null;
  /**
   * The what-if per-chart rating at these adjusted values, for display only
   * — never sent to the backend as a goal condition (see plan §3.2: rating
   * is a derived display value, not an independent goal condition).
   */
  projectedRating: number | null;
}
