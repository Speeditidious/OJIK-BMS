import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  CLEAR_TYPE_TO_LAMP_NAME,
  RANK_ORDER,
  lampName,
  expLevel,
  resolveLevel,
  songRating,
  standardizeRating,
} from "./rating-calc-core.mjs";

const FLOAT_TOLERANCE = 1e-6;

function assertClose(actual, expected, message) {
  assert.ok(
    Math.abs(actual - expected) < FLOAT_TOLERANCE,
    `${message}: expected ${expected}, got ${actual} (diff ${Math.abs(actual - expected)})`,
  );
}

// ── Static constant sanity checks (not fixture-driven — these are plain
//    data structures, not calculations dumped from Python). ─────────────────

assert.deepEqual(RANK_ORDER, ["F", "E", "D", "C", "B", "A", "AA", "AAA", "MAX-", "MAX"]);

assert.equal(lampName(null), "NOPLAY");
assert.equal(lampName(undefined), "NOPLAY");
assert.equal(lampName(0), "NOPLAY");
assert.equal(lampName(99), "NOPLAY"); // unknown clear_type defaults to NOPLAY
assert.equal(lampName(7), "FC");
assert.equal(lampName(9), "MAX");
assert.deepEqual(Object.keys(CLEAR_TYPE_TO_LAMP_NAME).map(Number).sort((a, b) => a - b), [
  0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
]);

// ── Golden fixture tests — every record dumped by
//    api/scripts/dump_rating_fixtures.py must be exercised here. ────────────

const fixture = JSON.parse(
  readFileSync(new URL("./__fixtures__/rating-golden.json", import.meta.url), "utf8"),
);

let resolveLevelCount = 0;
for (const testCase of fixture.resolveLevelCases) {
  const cfg = fixture.configs[testCase.configKey];
  const actual = resolveLevel(testCase.fumenSha256, testCase.fumenMd5, testCase.lamp, testCase.originalLevel, cfg);
  assert.equal(
    actual,
    testCase.expectedLevel,
    `resolveLevel mismatch [${testCase.description}]: expected "${testCase.expectedLevel}", got "${actual}"`,
  );
  resolveLevelCount += 1;
}
assert.equal(resolveLevelCount, fixture.resolveLevelCases.length);
assert.ok(resolveLevelCount > 0, "resolveLevelCases fixture must not be empty");

let songRatingCount = 0;
for (const testCase of fixture.songRatingCases) {
  const cfg = fixture.configs[testCase.configKey];
  const actual = songRating(
    { level: testCase.level, lamp: testCase.lamp, rank: testCase.rank, bp: testCase.bp, rate: testCase.rate },
    cfg,
  );
  assertClose(actual, testCase.expectedSongRating, `songRating mismatch [${testCase.description}]`);
  songRatingCount += 1;
}
assert.equal(songRatingCount, fixture.songRatingCases.length);
assert.ok(songRatingCount > 0, "songRatingCases fixture must not be empty");

let standardizeCount = 0;
for (const testCase of fixture.standardizeCases) {
  const actualPlayerLevel = expLevel(testCase.totalExp, testCase.expLevelStep, testCase.maxLevel);
  assert.equal(
    actualPlayerLevel,
    testCase.expectedPlayerLevel,
    `expLevel mismatch [${testCase.description}]: expected ${testCase.expectedPlayerLevel}, got ${actualPlayerLevel}`,
  );

  const actualBmsForce = standardizeRating(testCase.rawTopN, actualPlayerLevel);
  assertClose(actualBmsForce, testCase.expectedBmsForce, `standardizeRating mismatch [${testCase.description}]`);
  standardizeCount += 1;
}
assert.equal(standardizeCount, fixture.standardizeCases.length);
assert.ok(standardizeCount > 0, "standardizeCases fixture must not be empty");

console.log(
  `rating-calc-core.test.mjs: OK `
  + `(${resolveLevelCount} resolveLevel + ${songRatingCount} songRating + ${standardizeCount} standardize fixture records)`,
);
