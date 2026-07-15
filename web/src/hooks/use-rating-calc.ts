import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { RatingCalcConfig } from "@/lib/rating-calc-core";
import type { RatingCalcParamsResponse } from "@/lib/ranking-types";

/**
 * Map the raw snake_case `/rankings/{slug}/calc-params` response into the
 * camelCase `RatingCalcConfig` shape consumed directly by `songRating`/
 * `base`/`bonus`/etc. from `rating-calc-core.mjs`.
 */
export function toRatingCalcConfig(raw: RatingCalcParamsResponse): RatingCalcConfig {
  return {
    cTable: raw.c_table,
    levelWeights: raw.level_weights,
    baseLampMult: raw.base_lamp_mult,
    upperLampBonus: raw.upper_lamp_bonus,
    rankMult: raw.rank_mult,
    bonus: {
      bpWeight: raw.bonus.bp_weight,
      rateWeight: raw.bonus.rate_weight,
      bpFloor: raw.bonus.bp_floor,
      bpSlope: raw.bonus.bp_slope,
      rateFloor: raw.bonus.rate_floor,
      rateSlope: raw.bonus.rate_slope,
    },
    levelOverrides: raw.level_overrides.map((override) => ({
      fumenSha256: override.fumen_sha256,
      fumenMd5: override.fumen_md5,
      lampToLevel: override.lamp_to_level,
      note: override.note,
    })),
  };
}

/** Data shape RatingCalculatorDialog (Task 3) will consume. */
export interface RatingCalcParamsData {
  /** Ready to pass straight into `songRating`/`base`/etc. from rating-calc-core.mjs. */
  config: RatingCalcConfig;
  topN: number;
  maxLevel: number;
  expLevelStep: number;
  configFingerprint: string;
}

/**
 * Fetch and cache the per-table rating-formula config needed to reconstruct
 * rating calculations client-side (powers Task 3's "what-if" calculator).
 *
 * `staleTime: Infinity` because this is static server config — it only
 * changes on server restart (see `RankingConfig` being loaded once at
 * process startup in `ranking_config.py`). Tradeoff: a long-lived browser
 * tab left open across a server config change/restart will keep showing
 * the stale `configFingerprint` (and stale calc params) until the tab is
 * reloaded. This is an accepted tradeoff for this feature — no polling or
 * websocket-based invalidation is implemented.
 */
export function useRatingCalcParams(tableSlug: string | null) {
  return useQuery<RatingCalcParamsData>({
    queryKey: ["rating-calc-params", tableSlug],
    queryFn: async () => {
      const raw = await api.get<RatingCalcParamsResponse>(
        `/rankings/${tableSlug}/calc-params`,
      );
      return {
        config: toRatingCalcConfig(raw),
        topN: raw.top_n,
        maxLevel: raw.max_level,
        expLevelStep: raw.exp_level_step,
        configFingerprint: raw.config_fingerprint,
      };
    },
    enabled: !!tableSlug,
    staleTime: Infinity,
  });
}
