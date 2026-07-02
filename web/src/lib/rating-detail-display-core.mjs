/**
 * Format the rank shown inside day-stat rating contribution cards.
 *
 * Rating-change cards intentionally show the grade label only. Score-update
 * sections use `MAX-{n}` when the max-minus gap is available.
 *
 * @param {string | null | undefined} rank
 * @param {number | null | undefined} _maxMinusScore
 * @param {number | null | undefined} clearType
 * @returns {string | null}
 */
export function formatRatingContributionCardRankLabel(rank, _maxMinusScore, clearType) {
  if (clearType === 9 && rank === "MAX-") return null;
  return rank ?? null;
}

/**
 * Returns the day-stat rating contribution cards that should be rendered.
 *
 * TOP-N drops are omitted in this compact sheet view. Entries are ordered by
 * the current rating contribution so the strongest records appear first.
 *
 * @param {Array<{
 *   value?: number | null,
 *   delta_rating?: number | null,
 *   is_in_top_n?: boolean,
 *   was_in_top_n?: boolean,
 *   title?: string | null,
 *   sha256?: string | null,
 *   md5?: string | null,
 * }>} entries
 * @returns {typeof entries}
 */
export function getDayStatRatingContributionEntries(entries) {
  return entries
    .filter((entry) => {
      if (entry.was_in_top_n === true && entry.is_in_top_n === false) return false;
      return (
        Math.abs(entry.delta_rating ?? 0) > 1e-9 ||
        (entry.was_in_top_n === false && entry.is_in_top_n === true)
      );
    })
    .sort((left, right) => (
      (right.value ?? 0) - (left.value ?? 0) ||
      String(left.title ?? "").localeCompare(String(right.title ?? "")) ||
      String(left.sha256 ?? left.md5 ?? "").localeCompare(String(right.sha256 ?? right.md5 ?? ""))
    ));
}

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
