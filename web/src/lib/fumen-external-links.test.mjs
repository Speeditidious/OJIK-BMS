import assert from "node:assert/strict";

const { buildFumenExternalLinkGroups } = await import("./fumen-external-links.ts");

const sha256 = "b".repeat(64);
const md5 = "a".repeat(32);

const complete = buildFumenExternalLinkGroups({ md5, sha256 });
assert.deepEqual(
  complete.map((group) => [group.labelKey, group.links.map((link) => [link.name, link.href, link.missingHashType])]),
  [
    ["fumen.detail.viewer", [
      ["ScoreViewer", `https://bms-score-viewer.pages.dev/view?md5=${md5}`, undefined],
      ["EZ2PATTERN", `https://ez2pattern.kr/bms/chart?sha256=${sha256}`, undefined],
    ]],
    ["fumen.detail.ir", [
      ["BMS-IR", `https://www.bms-ir.org/new/song?songmd5=${md5}&view=both`, undefined],
      ["LR2Archive", `https://lr2ir.com/charts/${md5}`, undefined],
      ["MinIR", `https://www.gaftalk.com/minir/#/viewer/song/${sha256}/0`, undefined],
      ["Mocha", `https://mocha-repository.info/song.php?sha256=${sha256}`, undefined],
    ]],
  ],
);

const missing = buildFumenExternalLinkGroups({ md5: null, sha256: null });
assert.equal(missing.length, 2);
assert.deepEqual(
  missing.flatMap((group) => group.links.map((link) => [link.name, link.href, link.missingHashType])),
  [
    ["ScoreViewer", undefined, "md5"],
    ["EZ2PATTERN", undefined, "sha256"],
    ["BMS-IR", undefined, "md5"],
    ["LR2Archive", undefined, "md5"],
    ["MinIR", undefined, "sha256"],
    ["Mocha", undefined, "sha256"],
  ],
);
