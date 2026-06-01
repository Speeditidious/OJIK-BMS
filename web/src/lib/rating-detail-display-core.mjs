/**
 * Adapt the current rank payload for the rating detail header.
 *
 * Historical views must not fall back to the current dan decoration. If the
 * snapshot response has not arrived yet, or the historical snapshot has no
 * cleared dan, show no dan instead of leaking the latest one.
 *
 * @param {{
 *   ratingAsOf: string | null | undefined,
 *   myRank: any,
 *   contributionData: any,
 * }} params
 * @returns {any}
 */
export function getDisplayedRatingRankData({ ratingAsOf, myRank, contributionData }) {
  if (!ratingAsOf || myRank?.status !== "ok") return myRank;

  const summary = contributionData?.summary;
  const historicalDan = Object.prototype.hasOwnProperty.call(contributionData ?? {}, "dan_decoration")
    ? contributionData.dan_decoration
    : null;

  if (!summary) {
    return {
      ...myRank,
      dan_decoration: historicalDan,
    };
  }

  return {
    ...myRank,
    exp: summary.exp,
    rating: summary.rating,
    rating_norm: summary.rating_norm,
    bms_force: summary.rating_norm,
    dan_decoration: historicalDan,
  };
}
