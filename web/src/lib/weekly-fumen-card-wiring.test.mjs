import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(here, "../components/weekly/WeeklyFumenCard.tsx"), "utf8");
const decoratedUsername = readFileSync(resolve(here, "../components/ranking/DecoratedUsername.tsx"), "utf8");

assert.match(source, /const myRecordRow = pages\.find\(\(record\) => record\.user_id === myUserId\)/);
assert.doesNotMatch(source, /dan_decoration:\s*null/);
assert.match(source, /const WEEKLY_RECORD_COLGROUP/);
assert.match(source, /style=\{\{ tableLayout: "fixed", minWidth: 720 \}\}/);
assert.match(source, /<WeeklyRecordHeader firstLabel=\{t\("weekly\.myRecordSection"\)\} isPinned \/>/);
assert.doesNotMatch(source, /<div className="px-2\.5 py-1\.5 bg-primary/);
assert.match(source, /pinned:\$\{pinnedRecord\.user_id\}/);
assert.match(source, /record:\$\{record\.user_id\}/);
assert.match(source, /border-b border-border\/30 cursor-pointer hover:bg-secondary\/30 transition-colors/);
assert.match(source, /\{isDetailExpanded && \(/);
assert.doesNotMatch(source, /!isPinned && isDetailExpanded/);
assert.match(source, /<td className="px-2 py-2 align-middle">/);
assert.match(source, /className="inline-flex shrink-0"/);
assert.match(source, /className="inline-flex max-w-full min-w-0 cursor-pointer"/);
assert.doesNotMatch(source, /className="[^"]*flex items-center gap-2 min-w-0 cursor-pointer[^"]*"/);
assert.match(decoratedUsername, /align-middle/);
assert.doesNotMatch(decoratedUsername, /align-bottom/);
