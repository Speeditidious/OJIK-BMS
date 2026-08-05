/**
 * Text color class for a 1-based rank position (e.g. in a leaderboard/table).
 * Ranks 1-3 get gold/silver/bronze accents; everything else falls back to
 * the muted foreground token. Light-mode base classes use darker shades for
 * contrast against a light background; `dark:` variants preserve the
 * original dark-mode look.
 */
export function rankClass(rank: number): string {
  if (rank === 1) return "text-amber-600 dark:text-yellow-400";
  if (rank === 2) return "text-zinc-500 dark:text-zinc-300";
  if (rank === 3) return "text-amber-800 dark:text-amber-600";
  return "text-muted-foreground";
}
