/**
 * Per-table config needed to reconstruct the rating calculation client-side.
 * camelCase mirror of `TableRankingConfig`/`BonusConfig`/`LevelOverride` in
 * `api/app/services/ranking_config.py`. Task 2's calc-params endpoint
 * returns this shape; Task 2's frontend types file should reuse/align with
 * it rather than redefining it.
 */
export interface RatingCalcBonusConfig {
  bpWeight: number;
  rateWeight: number;
  bpFloor: number;
  bpSlope: number;
  /** 0~1 scale (not raw 0-100). */
  rateFloor: number;
  rateSlope: number;
}

export interface RatingCalcLevelOverride {
  fumenSha256: string | null;
  fumenMd5: string | null;
  /** lamp name -> level key (must exist in `RatingCalcConfig.levelWeights`). */
  lampToLevel: Record<string, string>;
  note?: string | null;
}

export interface RatingCalcConfig {
  cTable: number;
  levelWeights: Record<string, number>;
  baseLampMult: Record<string, number>;
  upperLampBonus: Record<string, number>;
  rankMult: Record<string, number>;
  bonus: RatingCalcBonusConfig;
  levelOverrides: RatingCalcLevelOverride[];
}

/** Input to `songRating`. `rate` is the raw DB 0-100 value (not 0~1). */
export interface SongRatingInput {
  level: string;
  lamp: string;
  rank: string;
  bp: number | null | undefined;
  rate: number | null | undefined;
}

export declare const CLEAR_TYPE_TO_LAMP_NAME: Record<number, string>;

export declare const RANK_ORDER: string[];

export declare function lampName(clearType: number | null | undefined): string;

export declare function fBp(bp: number | null | undefined, floor: number, slope: number): number;

export declare function fRate(rate01: number | null | undefined, floor: number, slope: number): number;

export declare function base(level: string, lamp: string, rank: string, cfg: RatingCalcConfig): number;

export declare function bonus(
  bp: number | null | undefined,
  rate01: number | null | undefined,
  cfg: RatingCalcConfig,
): number;

export declare function resolveLevel(
  fumenSha256: string | null | undefined,
  fumenMd5: string | null | undefined,
  lamp: string,
  originalLevel: string,
  cfg: RatingCalcConfig,
): string;

export declare function songRating(params: SongRatingInput, cfg: RatingCalcConfig): number;

export declare function expLevel(totalExp: number, expLevelStep: number, maxLevel: number): number;

export declare function standardizeRating(rawTopN: number, playerLevel: number): number;
