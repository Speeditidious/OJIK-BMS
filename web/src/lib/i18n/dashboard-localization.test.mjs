import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

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
