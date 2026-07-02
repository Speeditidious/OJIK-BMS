import assert from "node:assert/strict";
import { mergeDayStatSheetPrefs } from "./day-stat-sheet-preferences-core.mjs";

const currentPrefs = {
  day_sheet_tables: ["satellite", "stella"],
  day_sheet_show_exp_info: true,
  day_sheet_show_rating_section: true,
  day_sheet_show_rating_info: true,
  day_sheet_show_record_section: true,
  day_sheet_update_visible: { clear: true, score: true, bp: true, combo: false },
  day_sheet_update_order: ["clear", "score", "bp", "combo"],
  day_sheet_update_fullwidth: ["score"],
  day_sheet_dan_order: ["Overjoy"],
  day_sheet_rating_order: ["exp_info", "rating_info"],
  day_sheet_show_note: false,
  day_sheet_rating_display_mode: "rating",
  day_sheet_clear_type_hidden: [1, 2],
  day_sheet_score_rank_hidden: ["F"],
};

const merged = mergeDayStatSheetPrefs(currentPrefs, {
  day_sheet_show_note: true,
});

assert.deepEqual(merged, {
  ...currentPrefs,
  day_sheet_show_note: true,
});

assert.deepEqual(currentPrefs.day_sheet_show_note, false);

console.log("day-stat-sheet-preferences-core tests passed");
