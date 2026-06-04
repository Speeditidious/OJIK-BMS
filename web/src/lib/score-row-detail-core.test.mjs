import assert from "node:assert/strict";

import {
  JUDGMENT_STYLE,
  arrangementColumnLabel,
  arrangementOptionLabel,
  laneIsWhiteKey,
} from "./score-row-detail-core.mjs";

// JUDGMENT_STYLE has all 6 keys
assert.deepEqual(
  Object.keys(JUDGMENT_STYLE).sort(),
  ["bad", "good", "great", "miss", "pgreat", "poor"],
);
assert.equal(Object.keys(JUDGMENT_STYLE).length, 6, "exactly 6 keys");

// arrangementOptionLabel
assert.equal(arrangementOptionLabel(null),     "NORMAL");
assert.equal(arrangementOptionLabel("MIRROR"), "MIRROR");
assert.equal(arrangementOptionLabel("RANDOM"), "RANDOM");
assert.equal(arrangementOptionLabel(""),       "");

// arrangementColumnLabel
assert.equal(
  arrangementColumnLabel("RANDOM", {
    option_label: "RANDOM",
    lane_groups: null,
    double_option_label: null,
    unavailable_reason: "lr2_seed_unmapped",
  }),
  "RANDOM",
  "known option labels stay visible even when the lane arrangement is unavailable",
);
assert.equal(
  arrangementColumnLabel(null, {
    option_label: "UNKNOWN",
    lane_groups: null,
    double_option_label: null,
    unavailable_reason: "score_metadata_missing",
  }),
  null,
  "unknown metadata still renders as unavailable",
);

// laneIsWhiteKey — 7K SP
assert.equal(laneIsWhiteKey(7, 1), true,  "7K lane 1 is white");
assert.equal(laneIsWhiteKey(7, 2), false, "7K lane 2 is black");
assert.equal(laneIsWhiteKey(7, 3), true,  "7K lane 3 is white");
assert.equal(laneIsWhiteKey(7, 7), true,  "7K lane 7 is white");

// laneIsWhiteKey — 5K SP
assert.equal(laneIsWhiteKey(5, 5), true,  "5K lane 5 is white");
assert.equal(laneIsWhiteKey(5, 4), false, "5K lane 4 is black");
assert.equal(laneIsWhiteKey(5, 1), true,  "5K lane 1 is white");

// laneIsWhiteKey — 14K DP (P2 side lanes 8-14 mirror P1)
assert.equal(laneIsWhiteKey(14, 8),  true,  "14K lane 8 (P2 lane 1) is white");
assert.equal(laneIsWhiteKey(14, 9),  false, "14K lane 9 (P2 lane 2) is black");
assert.equal(laneIsWhiteKey(14, 14), true,  "14K lane 14 (P2 lane 7) is white");
