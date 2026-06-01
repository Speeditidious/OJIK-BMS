import type { MyRankData, RankingContributionResponse } from "./ranking-types";

export function getDisplayedRatingRankData(params: {
  ratingAsOf: string | null | undefined;
  myRank: MyRankData | null | undefined;
  contributionData: RankingContributionResponse | null | undefined;
}): MyRankData | null | undefined;
