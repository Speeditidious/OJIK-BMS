import assert from "node:assert/strict";

import { shouldToggleFumenRow } from "./fumen-row-toggle-core.mjs";

function targetMatching(match) {
  return {
    closest(selector) {
      return selector.includes(match) ? { tagName: match } : null;
    },
  };
}

assert.equal(shouldToggleFumenRow({ closest: () => null }), true);
assert.equal(shouldToggleFumenRow(targetMatching("a")), false);
assert.equal(shouldToggleFumenRow(targetMatching("button")), false);
assert.equal(shouldToggleFumenRow(targetMatching("[data-state]")), true);
assert.equal(shouldToggleFumenRow(targetMatching("[data-rating-cell]")), false);
