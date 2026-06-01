/**
 * Pure utility functions for FumenRowDetail display logic.
 * No React dependency — safe to use in both Node tests and browser code.
 */

/**
 * Tailwind text color class for each judgment key.
 * @type {Record<string, { color: string }>}
 */
export const JUDGMENT_STYLE = {
  pgreat: { color: "text-emerald-400" },
  great:  { color: "text-blue-400" },
  good:   { color: "text-orange-400" },
  bad:    { color: "text-red-400" },
  poor:   { color: "text-purple-400" },
  miss:   { color: "text-gray-400" },
};

/**
 * Maps unavailable-reason codes to their i18n translation keys.
 * @type {Record<string, string>}
 */
export const ARRANGEMENT_REASON_I18N_KEY = {
  score_metadata_missing:   "fumenRowDetail.unavailableReason.score_metadata_missing",
  keymode_missing:          "fumenRowDetail.unavailableReason.keymode_missing",
  lr2_seed_unmapped:        "fumenRowDetail.unavailableReason.lr2_seed_unmapped",
  static_map_unsupported:   "fumenRowDetail.unavailableReason.static_map_unsupported",
  assist_option_unsupported:"fumenRowDetail.unavailableReason.assist_option_unsupported",
  keymode_unsupported:      "fumenRowDetail.unavailableReason.keymode_unsupported",
  dp_unsupported:           "fumenRowDetail.unavailableReason.dp_unsupported",
};

/**
 * Return a display label for an arrangement option.
 * @param {string | null} optionLabel
 * @returns {string}
 */
export function arrangementOptionLabel(optionLabel) {
  return optionLabel ?? "NORMAL";
}

/**
 * Whether a given lane index should render as a white key for the given keymode.
 *
 * BMS lane numbering: scratch is lane 0, playable keys start at 1.
 * For 5K and 7K (SP), white keys are odd lanes (1,3,5,7), black keys are even (2,4,6).
 * For 10K / 14K (DP), the same pattern applies per-side:
 *   P1 side: lanes 1–7 follow SP coloring (odd=white).
 *   P2 side: lanes 8–14 map to 1–7 by subtracting 7, then follow SP coloring.
 *
 * @param {number} keymode  - Number of playable keys (5, 7, 10, 14, …)
 * @param {number} laneIndex - 1-based lane index as provided by the server
 * @returns {boolean}
 */
export function laneIsWhiteKey(keymode, laneIndex) {
  if (keymode === 10 || keymode === 14) {
    // DP: map P2 side (lanes 8-14) back to 1-7
    const normalized = laneIndex > 7 ? laneIndex - 7 : laneIndex;
    return normalized % 2 === 1;
  }
  // SP (5K, 7K, and others): odd = white
  return laneIndex % 2 === 1;
}
