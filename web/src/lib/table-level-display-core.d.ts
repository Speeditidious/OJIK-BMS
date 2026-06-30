export interface TableLevelDisplayParams {
  tableSlug?: string | null;
  tableName?: string | null;
  tableSymbol?: string | null;
  level: string | null | undefined;
}

export function formatTableLevelForDisplay(params: TableLevelDisplayParams): string;

export function formatTableLevelWithSymbolForDisplay(params: TableLevelDisplayParams): string;
