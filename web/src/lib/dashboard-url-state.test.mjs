import assert from "node:assert/strict";
import test from "node:test";

import { getDashboardRankingTable, mergeDashboardParams } from "./dashboard-url-state.mjs";

test("ranking table fallback is kept out of the URL", () => {
  const params = new URLSearchParams("tab=calendar");

  assert.equal(getDashboardRankingTable(params, "aery"), "aery");
  assert.equal(params.toString(), "tab=calendar");
});

test("explicit ranking table selection is written to the URL", () => {
  const params = mergeDashboardParams("tab=rating", { ranking_table: "satellite" });

  assert.equal(params.toString(), "tab=rating&ranking_table=satellite");
});
