/**
 * Return the ranking table selected in the dashboard URL, falling back without
 * mutating the URL state.
 *
 * @param {URLSearchParams} params
 * @param {string | null | undefined} fallbackSlug
 * @returns {string | null}
 */
export function getDashboardRankingTable(params, fallbackSlug) {
  return params.get("ranking_table") ?? fallbackSlug ?? null;
}

/**
 * Merge dashboard query-string updates into a new URLSearchParams instance.
 *
 * @param {string | URLSearchParams} currentParams
 * @param {Record<string, string | null>} updates
 * @returns {URLSearchParams}
 */
export function mergeDashboardParams(currentParams, updates) {
  const params = new URLSearchParams(currentParams.toString());
  for (const [key, value] of Object.entries(updates)) {
    if (value === null || value === "") params.delete(key);
    else params.set(key, value);
  }
  return params;
}
