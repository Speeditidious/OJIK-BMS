const SPECIAL_TABLE_ORDER = new Map([
  ["5aery", 0],
  ["7aery", 1],
  ["stella", 2],
  ["supernova", 2],
  ["st", 2],
  ["sn", 2],
  ["satellite", 3],
  ["solar", 3],
  ["sl", 3],
  ["so", 3],
  ["starlight", 4],
  ["sr", 4],
  ["overjoy", 5],
  ["★★", 5],
  ["balgwang", 6],
  ["★", 6],
  ["new_balgwang", 7],
  ["▼", 7],
]);

function levelNumber(level) {
  const match = String(level ?? "").match(/-?\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : Number.NEGATIVE_INFINITY;
}

function tableOrderKey(entry) {
  const slug = String(entry?.slug ?? "").trim();
  const symbol = String(entry?.symbol ?? "").trim();
  const specialOrder = SPECIAL_TABLE_ORDER.get(slug) ?? SPECIAL_TABLE_ORDER.get(symbol);
  if (specialOrder != null) {
    return [0, specialOrder, ""];
  }
  return [1, 0, symbol || slug];
}

export function compareTableLevelCore(a, b) {
  const aTable = tableOrderKey(a);
  const bTable = tableOrderKey(b);
  for (let i = 0; i < aTable.length; i++) {
    if (aTable[i] < bTable[i]) return -1;
    if (aTable[i] > bTable[i]) return 1;
  }

  const numberDiff = levelNumber(b?.level) - levelNumber(a?.level);
  if (numberDiff !== 0) return numberDiff;

  return String(a?.level ?? "").localeCompare(String(b?.level ?? ""));
}

export function sortTableLevelsCore(levels) {
  return [...levels].sort(compareTableLevelCore);
}

export function compareByTableLevelsCore(a, b) {
  const sortedA = sortTableLevelsCore(a);
  const sortedB = sortTableLevelsCore(b);
  const len = Math.max(sortedA.length, sortedB.length);
  for (let i = 0; i < len; i++) {
    if (i >= sortedA.length) return 1;
    if (i >= sortedB.length) return -1;
    const cmp = compareTableLevelCore(sortedA[i], sortedB[i]);
    if (cmp !== 0) return cmp;
  }
  return 0;
}
