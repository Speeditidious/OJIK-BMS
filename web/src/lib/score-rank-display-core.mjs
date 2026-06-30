/**
 * Pure helpers for score-rank display.
 */

/** @type {Record<string, number>} */
export const RANK_SORT_ORDER = {
  "MAX-": -1,
  AAA: 0,
  AA: 1,
  A: 2,
  B: 3,
  C: 4,
  D: 5,
  E: 6,
  F: 7,
};

export function formatScoreRankLabel(rank, maxMinusScore) {
  if (rank == null) return null;
  if (rank === "MAX-" && typeof maxMinusScore === "number" && Number.isFinite(maxMinusScore)) {
    return `MAX-${maxMinusScore}`;
  }
  return rank;
}

export function rankClassToken(rank) {
  if (rank === "MAX-") return "MAX-minus";
  return rank ?? "F";
}
