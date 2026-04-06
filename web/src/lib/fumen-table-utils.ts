import type { ClipboardEvent } from "react";
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

/**
 * Returns an onCopy handler for a fumen list table.
 * - Builds TSV from only the selected rows (Range.intersectsNode).
 * - The title cell (titleCellIndex) must have data-title / data-artist attributes.
 *   Its value is written as "title\nartist" (RFC 4180 quoting) so Excel treats it
 *   as a single cell with an in-cell line break.
 */
export function makeTableCopyHandler(
  titleCellIndex: number,
  rowSelector = "tbody tr[data-index]",
) {
  return (e: ClipboardEvent<HTMLTableElement>) => {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return;

    const range = selection.getRangeAt(0);
    const trs = Array.from(
      e.currentTarget.querySelectorAll<HTMLTableRowElement>(rowSelector)
    );
    const selectedRows = trs.filter((tr) => range.intersectsNode(tr));
    if (selectedRows.length === 0) return;

    const lines = selectedRows.map((tr) => {
      const cells = Array.from(tr.querySelectorAll("td"));
      return cells
        .map((td, i) => {
          if (i === titleCellIndex) {
            const title = td.dataset.title ?? "";
            const artist = td.dataset.artist ?? "";
            const raw = artist ? `${title}\n${artist}` : title;
            // RFC 4180: wrap in quotes, escape inner quotes as ""
            return `"${raw.replace(/"/g, '""')}"`;
          }
          return td.textContent?.trim() ?? "";
        })
        .join("\t");
    }).join("\n");

    e.clipboardData.setData("text/plain", lines);
    e.preventDefault();
  };
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
