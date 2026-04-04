import * as XLSX from "xlsx";

export const CLEAR_ROW_CLASS: Record<number, string> = {
  0: "clear-row-0",
  1: "clear-row-1",
  2: "clear-row-2",
  3: "clear-row-3",
  4: "clear-row-4",
  5: "clear-row-5",
  6: "clear-row-6",
  7: "clear-row-7",
  8: "clear-row-8",
  9: "clear-row-9",
};

export const ARRANGEMENT_KANJI: Record<string, string> = {
  NORMAL:        "正",
  MIRROR:        "鏡",
  RANDOM:        "乱",
  "R-RANDOM":    "R乱",
  "S-RANDOM":    "S乱",
  SPIRAL:        "螺",
  "H-RANDOM":    "H乱",
  "ALL-SCRATCH": "全皿",
  "EX-RAN":      "EX乱",
  "EX-S-RAN":    "EXS乱",
};

const LR2_ARRANGEMENT_NAMES = [
  "NORMAL", "MIRROR", "RANDOM", "S-RANDOM", "H-RANDOM", "ALL-SCRATCH",
] as const;

const BEA_ARRANGEMENT_NAMES = [
  "NORMAL", "MIRROR", "RANDOM", "R-RANDOM", "S-RANDOM",
  "SPIRAL", "H-RANDOM", "ALL-SCRATCH", "EX-RAN", "EX-S-RAN",
] as const;

export function parseArrangement(
  options: Record<string, unknown> | null,
  clientType: string | null
): string | null {
  if (!options) return null;
  if (clientType === "lr2") {
    const opBest = options.op_best;
    if (typeof opBest !== "number") return null;
    const idx = Math.floor(opBest / 10);
    return LR2_ARRANGEMENT_NAMES[idx] ?? null;
  }
  if (clientType === "beatoraja") {
    const option = options.option;
    if (typeof option !== "number") return null;
    return BEA_ARRANGEMENT_NAMES[option] ?? null;
  }
  return null;
}

export function levelSortIndex(level: string, levelOrder: string[]): number {
  const idx = levelOrder.indexOf(level);
  return idx >= 0 ? idx : 9999;
}

export function exportToExcel(
  data: Record<string, unknown>[],
  columns: { key: string; header: string }[],
  filename: string
): void {
  const rows = data.map((item) => {
    const row: Record<string, unknown> = {};
    for (const col of columns) {
      row[col.header] = item[col.key] ?? "";
    }
    return row;
  });
  const worksheet = XLSX.utils.json_to_sheet(rows, {
    header: columns.map((c) => c.header),
  });
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, "Sheet1");
  XLSX.writeFile(workbook, filename.endsWith(".xlsx") ? filename : `${filename}.xlsx`);
}
