import {
  formatTableLevelForDisplay as coreFormatTableLevelForDisplay,
  formatTableLevelWithSymbolForDisplay as coreFormatTableLevelWithSymbolForDisplay,
} from "./table-level-display-core.mjs";

export interface TableLevelDisplayParams {
  tableSlug?: string | null;
  tableName?: string | null;
  tableSymbol?: string | null;
  level: string | null | undefined;
}

function normalizeParams(params: TableLevelDisplayParams) {
  return {
    tableSlug: params.tableSlug ?? null,
    tableName: params.tableName ?? null,
    tableSymbol: params.tableSymbol ?? null,
    level: params.level,
  };
}

export function formatTableLevelForDisplay(params: TableLevelDisplayParams): string {
  return coreFormatTableLevelForDisplay(normalizeParams(params));
}

export function formatTableLevelWithSymbolForDisplay(params: TableLevelDisplayParams): string {
  return coreFormatTableLevelWithSymbolForDisplay(normalizeParams(params));
}
