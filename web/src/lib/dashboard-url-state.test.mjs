import assert from "node:assert/strict";
import test from "node:test";

import { buildDashboardUrl, getDashboardRankingTable, mergeDashboardParams } from "./dashboard-url-state.mjs";

test("ranking table fallback is kept out of the URL", () => {
  const params = new URLSearchParams("tab=calendar");

  assert.equal(getDashboardRankingTable(params, "aery"), "aery");
  assert.equal(params.toString(), "tab=calendar");
});

test("explicit ranking table selection is written to the URL", () => {
  const params = mergeDashboardParams("tab=rating", { ranking_table: "satellite" });

  assert.equal(params.toString(), "tab=rating&ranking_table=satellite");
});

test("dashboard URL builder keeps the visible dynamic route path", () => {
  const url = buildDashboardUrl(
    "/users/real-user-id/dashboard",
    "tab=distribution&d_tbl=table-1",
    { d_lv: "12", d_ct: "5" },
  );

  assert.equal(url, "/users/real-user-id/dashboard?tab=distribution&d_tbl=table-1&d_lv=12&d_ct=5");
});

test("dashboard URL builder omits the question mark when all params are removed", () => {
  const url = buildDashboardUrl(
    "/users/real-user-id/dashboard",
    "d_lv=12",
    { d_lv: null },
  );

  assert.equal(url, "/users/real-user-id/dashboard");
});
