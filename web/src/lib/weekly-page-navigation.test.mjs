import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const pageSource = readFileSync(new URL("../app/weekly/page.tsx", import.meta.url), "utf8");

test("weekly page keeps period navigation available when detail data is missing", () => {
  assert.match(pageSource, /displayPeriod/);
  assert.doesNotMatch(pageSource, /\{detail && \(\s*<WeeklyPeriodNav/);
  assert.match(pageSource, /periodStart=\{displayPeriod\.periodStart\}/);
  assert.match(pageSource, /periodEnd=\{displayPeriod\.periodEnd\}/);
});

test("weekly page restores stored category and bracket with the current period on initial entry", () => {
  assert.match(pageSource, /readLastWeekly\(user\?\.id\)/);
  assert.match(pageSource, /updateParams\(\{ category: resolved\.category, bracket: resolved\.bracket, offset: "0" \}\)/);
  assert.doesNotMatch(pageSource, /saveLastWeekly\(user\?\.id,\s*\{[^}]*offset/s);
});

test("weekly page keeps the selected period when switching category or bracket", () => {
  assert.match(
    pageSource,
    /updateParams\(\{ category: c, bracket: firstBracket \}\)/,
  );
  assert.match(pageSource, /onSelect=\{\(b\) => updateParams\(\{ bracket: b \}\)\}/);
  assert.doesNotMatch(pageSource, /onSelect=\{\(c\) => \{[\s\S]*offset: "0"/);
  assert.doesNotMatch(pageSource, /onSelect=\{\(b\) => updateParams\(\{ bracket: b, offset: "0" \}\)\}/);
});
