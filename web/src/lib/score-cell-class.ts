import { rankClassToken } from "@/lib/score-rank-display-core.mjs";

/** Returns CSS class for a clear-type <td> (references globals.css clear-cell-*) */
export function clearTdClass(clearType: number | null | undefined, dim = false): string {
  const ct = clearType ?? 0;
  // NO PLAY(0) is already dimmed — no dim variant needed
  return (dim && ct !== 0) ? `clear-cell-${ct}-dim` : `clear-cell-${ct}`;
}

/** Returns CSS class for a rank-based <td> (references globals.css rank-cell-*) */
export function rankTdClass(rank: string | null | undefined, dim = false): string {
  const r = rankClassToken(rank);
  // F is already dimmed — no dim variant needed
  return (dim && r !== "F") ? `rank-cell-${r}-dim` : `rank-cell-${r}`;
}
