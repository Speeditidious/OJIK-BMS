import type { MyRankData, RankingContributionResponse } from "./ranking-types";

export function formatRatingContributionCardRankLabel(
  rank: string | null | undefined,
  maxMinusScore: number | null | undefined,
): string | null;

export function getDisplayedRatingRankData(params: {
  ratingAsOf: string | null | undefined;
  myRank: MyRankData | null | undefined;
  contributionData: RankingContributionResponse | null | undefined;
}): MyRankData | null | undefined;
