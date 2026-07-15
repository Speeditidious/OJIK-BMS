/**
 * Client-side "what-if" rating calculator core.
 *
 * 1:1 JS port of the per-chart rating formula implemented in
 * `api/app/services/ranking_calculator.py`. Kept as pure functions (no
 * React, no fetch) so the calculator popup can recompute a chart's rating
 * on every keystroke with zero server round-trips.
 *
 * IMPORTANT: this file must be kept byte-for-byte equivalent (within float
 * tolerance) to the Python source. `rating-calc-core.test.mjs` verifies this
 * against golden fixtures dumped from Python by
 * `api/scripts/dump_rating_fixtures.py` — re-run that script and re-run
 * this test whenever `ranking_calculator.py`'s formula changes.
 */

/**
 * Clear-type integer -> lamp name. Mirrors Python's
 * `CLEAR_TYPE_TO_LAMP_NAME` in `ranking_calculator.py`. LR2 and Beatoraja
 * share the same clear_type integer encoding.
 * @type {Record<number, string>}
 */
export const CLEAR_TYPE_TO_LAMP_NAME = {
  0: "NOPLAY",
  1: "FAILED",
  2: "ASSIST",
  3: "EASY",
  4: "NORMAL",
  5: "HARD",
  6: "EXHARD",
  7: "FC",
  8: "PERFECT",
  9: "MAX",
};

/**
 * Rank ordering, weakest to strongest. Same order as Python's `RANK_ORDER`.
 * @type {string[]}
 */
export const RANK_ORDER = ["F", "E", "D", "C", "B", "A", "AA", "AAA", "MAX-", "MAX"];

/** FC-or-above lamps — same set as Python's `_FC_OR_ABOVE`. */
const FC_OR_ABOVE = new Set(["FC", "PERFECT", "MAX"]);

/**
 * Map a clear_type integer to its lamp name, defaulting unknown/null values
 * to "NOPLAY". Mirrors Python's `_lamp_name`.
 *
 * @param {number | null | undefined} clearType
 * @returns {string}
 */
export function lampName(clearType) {
  if (clearType === null || clearType === undefined) return "NOPLAY";
  return CLEAR_TYPE_TO_LAMP_NAME[clearType] ?? "NOPLAY";
}

/**
 * BP easing curve (cosine). bp >= floor -> 0, bp = 0 -> 1. Port of `_f_bp`.
 *
 * @param {number | null | undefined} bp
 * @param {number} floor
 * @param {number} slope
 * @returns {number}
 */
export function fBp(bp, floor, slope) {
  if (bp === null || bp === undefined || bp < 0 || bp >= floor) return 0.0;
  const x = ((floor - bp) / floor) ** slope;
  return Math.min((1 - Math.cos(Math.PI * x)) / 2, 1.0);
}

/**
 * Rate easing curve (cosine). rate01 in 0~1 scale. rate01 <= floor -> 0,
 * rate01 = 1.0 -> 1. Port of `_f_rate`.
 *
 * @param {number | null | undefined} rate01
 * @param {number} floor
 * @param {number} slope
 * @returns {number}
 */
export function fRate(rate01, floor, slope) {
  if (rate01 === null || rate01 === undefined || rate01 <= floor) return 0.0;
  const x = ((rate01 - floor) / (1 - floor)) ** slope;
  return Math.min((1 - Math.cos(Math.PI * x)) / 2, 1.0);
}

/**
 * Base rating component (without C_table). Port of `_base`.
 *
 * `rank` in {"MAX", "MAX-"} remaps to the "AAA" key for the `rankMult`
 * lookup. Missing `level` in `cfg.levelWeights` returns 0.
 *
 * @param {string} level
 * @param {string} lamp
 * @param {string} rank
 * @param {import("./rating-calc-core.d.ts").RatingCalcConfig} cfg
 * @returns {number}
 */
export function base(level, lamp, rank, cfg) {
  if (!Object.prototype.hasOwnProperty.call(cfg.levelWeights, level)) return 0.0;
  const levelWeight = cfg.levelWeights[level];
  const rankMultiplierKey = rank === "MAX" || rank === "MAX-" ? "AAA" : rank;
  return (
    cfg.baseLampMult[lamp]
    * (cfg.rankMult[rankMultiplierKey] ?? 0.0)
    * (levelWeight + cfg.upperLampBonus[lamp])
  );
}

/**
 * Bonus rating component (without C_table). `rate01` is already normalized
 * to 0~1. Port of `_bonus`.
 *
 * @param {number | null | undefined} bp
 * @param {number | null | undefined} rate01
 * @param {import("./rating-calc-core.d.ts").RatingCalcConfig} cfg
 * @returns {number}
 */
export function bonus(bp, rate01, cfg) {
  return (
    cfg.bonus.bpWeight * fBp(bp, cfg.bonus.bpFloor, cfg.bonus.bpSlope)
    + cfg.bonus.rateWeight * fRate(rate01, cfg.bonus.rateFloor, cfg.bonus.rateSlope)
  );
}

/**
 * Apply `cfg.levelOverrides` for a fumen+lamp combination. Port of
 * `_resolve_level`.
 *
 * Matching rules (CLAUDE.md "Fumen hash lookups"): an override's
 * `fumenSha256` matching `fumenSha256` takes priority; otherwise the
 * override's `fumenMd5` matching `fumenMd5` applies (LR2 fallback, only
 * when the sha256 check didn't already match).
 *
 * @param {string | null | undefined} fumenSha256
 * @param {string | null | undefined} fumenMd5
 * @param {string} lamp
 * @param {string} originalLevel
 * @param {import("./rating-calc-core.d.ts").RatingCalcConfig} cfg
 * @returns {string}
 */
export function resolveLevel(fumenSha256, fumenMd5, lamp, originalLevel, cfg) {
  for (const ov of cfg.levelOverrides) {
    const shaMatch = (
      ov.fumenSha256 != null
      && fumenSha256 != null
      && ov.fumenSha256 === fumenSha256
    );
    const md5Match = (
      !shaMatch
      && ov.fumenMd5 != null
      && fumenMd5 != null
      && ov.fumenMd5 === fumenMd5
    );
    if (shaMatch || md5Match) {
      return ov.lampToLevel[lamp] ?? originalLevel;
    }
  }
  return originalLevel;
}

/**
 * Per-chart rating = C_table x (Base + Bonus). Port of `_song_rating`.
 *
 * `rate` is the raw DB 0-100 value (normalized to 0-1 internally before
 * calling `bonus`). `lamp === "NOPLAY"` or an unknown `level` returns 0.
 * FC-or-above lamps (FC, PERFECT, MAX) force `effectiveBp = 0` regardless
 * of the passed `bp`.
 *
 * @param {{
 *   level: string,
 *   lamp: string,
 *   rank: string,
 *   bp: number | null | undefined,
 *   rate: number | null | undefined,
 * }} params
 * @param {import("./rating-calc-core.d.ts").RatingCalcConfig} cfg
 * @returns {number}
 */
export function songRating({ level, lamp, rank, bp, rate }, cfg) {
  if (lamp === "NOPLAY" || !Object.prototype.hasOwnProperty.call(cfg.levelWeights, level)) return 0.0;
  const rate01 = rate === null || rate === undefined ? null : rate / 100.0;
  const effectiveBp = FC_OR_ABOVE.has(lamp) ? 0.0 : bp;
  return cfg.cTable * (base(level, lamp, rank, cfg) + bonus(effectiveBp, rate01, cfg));
}

/**
 * EXP -> player level. threshold(n) = K x n x (n+1), capped at maxLevel.
 * Port of `_exp_level`, including the float-error safety while-loop.
 *
 * @param {number} totalExp
 * @param {number} expLevelStep
 * @param {number} maxLevel
 * @returns {number}
 */
export function expLevel(totalExp, expLevelStep, maxLevel) {
  if (totalExp <= 0) return 0;
  const step = expLevelStep;
  const maxThreshold = step * maxLevel * (maxLevel + 1);
  if (totalExp >= maxThreshold) return maxLevel;
  let n = Math.trunc((-1 + Math.sqrt(1 + (4 * totalExp) / step)) / 2);
  while (step * (n + 1) * (n + 2) <= totalExp) n += 1;
  return Math.min(n, maxLevel);
}

/**
 * BMSFORCE — standardized rating. Port of `standardize_rating`.
 *
 * adjusted = rawTopN x (1 + playerLevel x 0.0001)
 * if adjusted <= 100_000: bmsForce = adjusted / 5000
 * else: bmsForce = 20 + sqrt(4 x ((adjusted - 100_000) / 5000 + 1)) - 2
 *
 * @param {number} rawTopN
 * @param {number} playerLevel
 * @returns {number}
 */
export function standardizeRating(rawTopN, playerLevel) {
  if (rawTopN <= 0) return 0.0;
  const adjusted = rawTopN * (1 + playerLevel * 0.0001);
  if (adjusted <= 100000) return adjusted / 5000.0;
  return 20.0 + Math.sqrt(4 * ((adjusted - 100000) / 5000.0 + 1)) - 2.0;
}
