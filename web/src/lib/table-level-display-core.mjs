function isAeryTable({ tableSlug, tableName, tableSymbol } = {}) {
  return (
    tableSlug === "5aery"
    || tableSlug === "7aery"
    || tableName === "5KEYS AERY"
    || tableName === "7KEYS AERY"
    || tableSymbol === "⑤"
    || tableSymbol === "⑦"
  );
}

export function formatTableLevelForDisplay({ tableSlug, tableName, tableSymbol, level }) {
  const rawLevel = String(level ?? "").trim();
  if (!isAeryTable({ tableSlug, tableName, tableSymbol })) return rawLevel;
  return rawLevel.replace(/^LEVEL\s+/i, "");
}

export function formatTableLevelWithSymbolForDisplay({ tableSlug, tableName, tableSymbol, level }) {
  const displayLevel = formatTableLevelForDisplay({ tableSlug, tableName, tableSymbol, level });
  if (!tableSymbol) return displayLevel;
  return `${tableSymbol}${displayLevel.replace(tableSymbol, "")}`;
}
