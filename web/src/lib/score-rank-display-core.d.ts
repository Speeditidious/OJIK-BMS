export const RANK_SORT_ORDER: Record<string, number>;
export function formatScoreRankLabel(
  rank: string | null | undefined,
  maxMinusScore: number | null | undefined,
): string | null;
export function rankClassToken(rank: string | null | undefined): string;
