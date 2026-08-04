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

test("day detail stat uncertainty tooltips exist in all locales", () => {
  for (const lang of ["ko", "en", "ja"]) {
    const dayDetail = resources[lang].translation.dashboard.dayDetail;
    for (const key of [
      "playCountUncertain",
      "playCountUnsyncedDate",
      "playTimeUncertain",
      "playTimeUnsyncedDate",
      "notesHitUncertain",
      "notesHitUnsyncedDate",
    ]) {
      assert.ok(
        typeof dayDetail[key] === "string" && dayDetail[key].length > 0,
        `${lang} should have ${key} tooltip`,
      );
    }
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

test("goal filter, shared calendar, and snapshot keys exist in all locales", () => {
  const filterKeys = [
    "title", "level", "clear", "rank", "rate", "bp",
    "createdRange", "achievedRange",
    "reset", "noMatch", "min", "max", "anyDate", "clearDates", "invalidRange",
    "activeCount", "chartAxis", "courseAxis", "table", "applyLevelDisplayPrefs", "showAxis",
    "noneSpecified", "axisEmpty",
  ];
  const calendarKeys = ["prevMonth", "nextMonth", "start", "end"];

  for (const lang of ["ko", "en", "ja"]) {
    const goals = resources[lang].translation.goals;
    assert.ok(goals.filter, `${lang} should have goals.filter`);
    for (const key of filterKeys) {
      assert.equal(
        typeof goals.filter[key], "string",
        `${lang} goals.filter.${key} should be a string`,
      );
    }
    assert.equal(
      goals.filter.matched, undefined,
      `${lang} goals.filter.matched should be removed`,
    );
    assert.equal(goals.filter.combineLabel, undefined, `${lang} goals.filter.combineLabel`);
    assert.equal(goals.filter.combineAnd, undefined, `${lang} goals.filter.combineAnd`);
    assert.equal(goals.filter.combineOr, undefined, `${lang} goals.filter.combineOr`);
    assert.equal(typeof goals.panel.othersTitle, "string", `${lang} goals.panel.othersTitle`);
    assert.equal(
      typeof goals.panel.othersDescription, "string",
      `${lang} goals.panel.othersDescription`,
    );

    const calendar = resources[lang].translation.common.calendar;
    assert.ok(calendar, `${lang} should have common.calendar`);
    for (const key of calendarKeys) {
      assert.equal(
        typeof calendar[key], "string",
        `${lang} common.calendar.${key} should be a string`,
      );
    }

    assert.equal(
      typeof resources[lang].translation.dashboard.tableClear.snapshotLabel, "string",
      `${lang} dashboard.tableClear.snapshotLabel`,
    );
  }
});

test("the snapshot date picker has no hardcoded Korean chrome", () => {
  const source = readFileSync(
    new URL("../../components/dashboard/SnapshotDatePicker.tsx", import.meta.url),
    "utf8",
  );
  for (const literal of ["이전 달", "다음 달", "일\", \"월\"", "년 ", "월\"}"]) {
    assert.equal(
      source.includes(literal), false,
      `SnapshotDatePicker should not hardcode ${JSON.stringify(literal)}`,
    );
  }
});
