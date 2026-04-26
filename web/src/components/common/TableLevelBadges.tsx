"use client";

export interface TableLevelRef {
  symbol: string;
  slug: string;
  level: string;
}

export function compareByTableLevels(a: TableLevelRef[], b: TableLevelRef[]): number {
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i++) {
    if (i >= a.length) return 1;
    if (i >= b.length) return -1;
    const aLv = parseFloat(a[i].level) || 0;
    const bLv = parseFloat(b[i].level) || 0;
    if (aLv !== bLv) return bLv - aLv;
  }
  return 0;
}

interface Props {
  levels: TableLevelRef[];
  maxVisible?: number;
}

export function TableLevelBadges({ levels, maxVisible = 3 }: Props) {
  if (levels.length === 0) return <span className="text-label row-muted">-</span>;
  const visible = levels.slice(0, maxVisible);
  const rest = levels.length - visible.length;
  const text = visible.map(({ symbol, level }) => `${symbol}${level}`).join(", ");
  return (
    <span className="text-label">
      {text}
      {rest > 0 && <span className="text-caption row-muted"> +{rest}</span>}
    </span>
  );
}
