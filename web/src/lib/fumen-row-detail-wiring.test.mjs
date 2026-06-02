import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const read = (path) => readFileSync(resolve(here, path), "utf8");

const songDetail = read("../app/songs/SongDetailPage.tsx");
assert.match(songDetail, /FumenHistoryRowDetail/);
assert.match(songDetail, /expandedScoreIds/);
assert.doesNotMatch(songDetail, /t\("common\.fields\.env"\)/);

const contributionTable = read("../components/ranking/ContributionTable.tsx");
assert.match(contributionTable, /asOf=\{asOf\}/);
assert.match(contributionTable, /scoreId=\{entry\.detail_score_id\}/);
assert.match(contributionTable, /parseArrangement\(entry\.options \?\? null, entry\.client_type \?\? null\)/);
assert.doesNotMatch(contributionTable, /useScoreRowDetail/);

const ratingDetail = read("../components/ranking/RatingDetailSection.tsx");
assert.match(ratingDetail, /asOf=\{ratingAsOf\}/);

const scoreUpdates = read("../components/dashboard/ScoreUpdates.tsx");
assert.match(scoreUpdates, /<FumenTab data=\{data\} userId=\{userId\} asOf=\{date\}/);
assert.match(scoreUpdates, /function SummaryFumenRow/);
assert.match(scoreUpdates, /<FumenRowDetail fumenId=\{item\.fumen_id\} scoreId=\{item\.detail_score_id\} userId=\{userId\} asOf=\{asOf\}/);
assert.match(scoreUpdates, /<SummaryFumenRow item=\{item\} userId=\{userId\} asOf=\{asOf\}/);
assert.match(scoreUpdates, /<CategoryTab data=\{data\} userId=\{userId\} asOf=\{date\}/);
assert.match(scoreUpdates, /function CourseTableRow/);
assert.match(scoreUpdates, /<CourseRowDetail courseHash=\{item\.course_hash\} clientType=\{item\.client_type\} scoreId=\{item\.detail_score_id\} userId=\{userId\} asOf=\{asOf\}/);
assert.match(scoreUpdates, /<CourseTableRow key=\{i\} item=\{c\} userId=\{userId\} asOf=\{asOf\}/);
assert.match(scoreUpdates, /detail_score_id: string/);
assert.match(scoreUpdates, /const key = detail_score_id/);

for (const path of [
  "../components/songs/SongListTable.tsx",
  "../components/dashboard/TableClearSection.tsx",
  "../components/tables/TableDetail.tsx",
]) {
  const source = read(path);
  assert.match(source, /ref=\{rowVirtualizer\.measureElement\}/);
  assert.match(source, /useState<Set<string>>/);
}
