import type { MyRankData, RankingContributionResponse } from "./ranking-types";

export function formatRatingContributionCardRankLabel(
  rank: string | null | undefined,
  maxMinusScore: number | null | undefined,
  clearType?: number | null | undefined,
): string | null;

export function getDayStatRatingContributionEntries<T extends {
  value?: number | null;
  delta_rating?: number | null;
  is_in_top_n?: boolean;
  was_in_top_n?: boolean;
  title?: string | null;
  sha256?: string | null;
  md5?: string | null;
}>(entries: T[]): T[];

export function getDisplayedRatingRankData(params: {
  ratingAsOf: string | null | undefined;
  myRank: MyRankData | null | undefined;
  contributionData: RankingContributionResponse | null | undefined;
}): MyRankData | null | undefined;
