import assert from "node:assert/strict";

import {
  RANK_SORT_ORDER,
  formatScoreRankLabel,
  rankClassToken,
} from "./score-rank-display-core.mjs";

assert.equal(formatScoreRankLabel("MAX-", 17), "MAX-17");
assert.equal(formatScoreRankLabel("MAX-", 0), "MAX-0");
assert.equal(formatScoreRankLabel("MAX-", null), "MAX-");
assert.equal(formatScoreRankLabel("AAA", 17), "AAA");
assert.equal(formatScoreRankLabel(null, 17), null);

assert.equal(rankClassToken("MAX-"), "MAX-minus");
assert.equal(rankClassToken("AAA"), "AAA");
assert.equal(rankClassToken(null), "F");

assert.equal(RANK_SORT_ORDER["MAX-"] < RANK_SORT_ORDER.AAA, true);
