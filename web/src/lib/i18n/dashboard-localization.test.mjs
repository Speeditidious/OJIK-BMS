import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resources } from "../../lib/i18n/resources.mjs";

const userDashboardSource = readFileSync(
  new URL("../../components/dashboard/UserDashboardContent.tsx", import.meta.url),
  "utf8",
);
const scoreUpdatesSource = readFileSync(
  new URL("../../components/dashboard/ScoreUpdates.tsx", import.meta.url),
  "utf8",
);

test("dashboard overview labels are translated instead of hardcoded", () => {
  for (const literal of [
    "Clear Distribution",
    "Activity Summary",
    "Activity Calendar",
    "Activity Heatmap",
    "Activity Graph",
    "Rating Graph",
    "Back to activity summary",
    "Back to calendar",
  ]) {
    assert.equal(
      userDashboardSource.includes(`>${literal}<`) ||
        userDashboardSource.includes(`"${literal}"`),
      false,
      `${literal} should come from i18n resources`,
    );
  }
});

test("playerStatsUnreliable tooltip exists in all locales", () => {
  for (const lang of ["ko", "en", "ja"]) {
    const dayDetail = resources[lang].translation.dashboard.dayDetail;
    assert.ok(
      typeof dayDetail.playerStatsUnreliable === "string" && dayDetail.playerStatsUnreliable.length > 0,
      `${lang} should have playerStatsUnreliable tooltip`,
    );
  }
});

test("noPlayerStats tooltip exists in all locales", () => {
  for (const lang of ["ko", "en", "ja"]) {
    const stats = resources[lang].translation.dashboard.stats;
    assert.ok(
      typeof stats.noPlayerStats === "string" && stats.noPlayerStats.length > 0,
      `${lang} should have noPlayerStats tooltip`,
    );
  }
});

test("dashboard record detail labels are translated instead of hardcoded", () => {
  for (const literal of [
    "Record Details",
    "Update Summary",
    "Rating Changes",
    "All",
    "Course Records",
    "Max Combo Updates",
  ]) {
    assert.equal(
      scoreUpdatesSource.includes(`>${literal}<`) ||
        scoreUpdatesSource.includes(`"${literal}"`),
      false,
      `${literal} should come from i18n resources`,
    );
  }
});

test("day stat sheet labels use the current report wording", () => {
  assert.equal(
    resources.en.translation.dashboard.scoreUpdates.dayStatSheetTab,
    "Daily Report",
  );
  assert.equal(
    resources.en.translation.dashboard.scoreUpdates.imagePreviewTitle,
    "Daily Report Preview",
  );
  assert.equal(
    resources.ja.translation.dashboard.scoreUpdates.dayStatSheetTab,
    "デイリーレポート",
  );
  assert.equal(
    resources.ja.translation.dashboard.scoreUpdates.imagePreviewTitle,
    "デイリーレポートプレビュー",
  );
  assert.equal(
    resources.ja.translation.dashboard.daySheet.reportTitle,
    "デイリーレポート",
  );
});
