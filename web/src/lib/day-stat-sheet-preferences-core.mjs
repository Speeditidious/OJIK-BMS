/**
 * Returns a full Day Stat Sheet preference object with the requested changes
 * applied, so partial updates do not replace the stored nested preference bag.
 *
 * @template {object} T
 * @param {T} currentPrefs
 * @param {Partial<T>} nextPrefs
 * @returns {T}
 */
export function mergeDayStatSheetPrefs(currentPrefs, nextPrefs) {
  return { ...currentPrefs, ...nextPrefs };
}
