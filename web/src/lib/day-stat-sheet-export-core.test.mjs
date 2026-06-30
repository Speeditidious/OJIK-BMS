import assert from "node:assert/strict";
import test from "node:test";

import {
  getHeightSplitRanges,
  getSectionSplitGroups,
} from "./day-stat-sheet-export-core.mjs";

test("getSectionSplitGroups returns rating and record groups with profile included in both", () => {
  assert.deepEqual(
    getSectionSplitGroups(["profile", "summary", "rating", "record"]),
    [
      ["profile", "summary", "rating"],
      ["profile", "summary", "record"],
    ],
  );
});

test("getSectionSplitGroups falls back to one group when rating or record is unavailable", () => {
  assert.deepEqual(
    getSectionSplitGroups(["profile", "summary", "rating"]),
    [["profile", "summary", "rating"]],
  );
});

test("getHeightSplitRanges keeps blocks intact by default", () => {
  assert.deepEqual(
    getHeightSplitRanges(
      [
        { id: "profile", top: 0, bottom: 480 },
        { id: "rating", top: 500, bottom: 2300 },
        { id: "record", top: 2320, bottom: 4200 },
      ],
      { maxHeight: 3000, preserveBlocks: true },
    ),
    [
      { top: 0, bottom: 2300 },
      { top: 2320, bottom: 4200 },
    ],
  );
});

test("getHeightSplitRanges can split at exact height intervals", () => {
  assert.deepEqual(
    getHeightSplitRanges(
      [
        { id: "profile", top: 0, bottom: 480 },
        { id: "record", top: 500, bottom: 4200 },
      ],
      { maxHeight: 3000, preserveBlocks: false },
    ),
    [
      { top: 0, bottom: 3000 },
      { top: 3000, bottom: 4200 },
    ],
  );
});

test("getHeightSplitRanges keeps a title with the following block", () => {
  assert.deepEqual(
    getHeightSplitRanges(
      [
        { id: "profile", top: 0, bottom: 400 },
        { id: "title", top: 420, bottom: 470, keepWithNext: true },
        { id: "summary", top: 480, bottom: 760 },
      ],
      { maxHeight: 500, preserveBlocks: true },
    ),
    [
      { top: 0, bottom: 400 },
      { top: 420, bottom: 760 },
    ],
  );
});

test("getHeightSplitRanges avoids cutting through staggered two-column rows", () => {
  assert.deepEqual(
    getHeightSplitRanges(
      [
        { id: "left-header", top: 0, bottom: 40, keepWithNext: true },
        { id: "left-row-1", top: 40, bottom: 140 },
        { id: "left-row-2", top: 140, bottom: 240 },
        { id: "right-header", top: 0, bottom: 40, keepWithNext: true },
        { id: "right-row-1", top: 40, bottom: 170 },
        { id: "right-row-2", top: 170, bottom: 270 },
      ],
      { maxHeight: 150, preserveBlocks: true },
    ),
    [
      { top: 0, bottom: 270 },
    ],
  );
});
