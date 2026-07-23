import { RANK_ORDER } from "./rating-calc-core.mjs";

const RANK_INDEX = Object.fromEntries(RANK_ORDER.map((rank, index) => [rank, index]));

/**
 * Frontend port of `goal_evaluator.validate_goal_target` (plan §3.2) — the
 * immediate-feedback half of goal validation. The backend re-runs the same
 * rule authoritatively on POST /goals/, so this must stay behaviorally
 * identical: no selected metric may regress vs. baseline, and at least one
 * selected metric must be a genuine improvement.
 *
 * @param {{ clear_type: number|null, min_bp: number|null, rank: string|null, rate: number|null }} baseline
 * @param {{ clearType?: number|null, minBp?: number|null, rank?: string|null, rate?: number|null }} target
 * @returns {{ ok: boolean, errors: string[], improvedMetrics: string[] }}
 */
export function validateGoalTarget(baseline, target) {
  const errors = [];
  const improved = [];
  let selected = false;

  const targetClearType = target.clearType ?? null;
  const targetMinBp = target.minBp ?? null;
  const targetRank = target.rank ?? null;
  const targetRate = target.rate ?? null;

  if (targetClearType != null) {
    selected = true;
    const baseClear = baseline.clear_type ?? 0;
    if (targetClearType < baseClear) errors.push("clear_type_worse");
    else if (targetClearType > baseClear) improved.push("clear_type");
  }

  if (targetMinBp != null) {
    selected = true;
    if (baseline.min_bp != null) {
      if (targetMinBp > baseline.min_bp) errors.push("min_bp_worse");
      else if (targetMinBp < baseline.min_bp) improved.push("min_bp");
    }
  }

  if (targetRank != null) {
    selected = true;
    const baseRankPos = baseline.rank ? (RANK_INDEX[baseline.rank] ?? -1) : -1;
    const targetRankPos = RANK_INDEX[targetRank];
    if (targetRankPos == null) errors.push("invalid_rank");
    else if (targetRankPos < baseRankPos) errors.push("rank_worse");
    else if (targetRankPos > baseRankPos) improved.push("rank");
  }

  if (targetRate != null) {
    selected = true;
    const baseRate = baseline.rate ?? 0;
    if (targetRate < baseRate) errors.push("rate_worse");
    else if (targetRate > baseRate) improved.push("rate");
  }

  if (!selected) errors.push("no_metric_selected");
  else if (errors.length === 0 && improved.length === 0) errors.push("no_improvement");

  const ok = selected && errors.length === 0 && improved.length > 0;
  return { ok, errors, improvedMetrics: improved };
}
