"use client";

import { cn } from "@/lib/utils";
import type { RankingTableConfig } from "@/lib/ranking-types";

interface RankingTableSelectorProps {
  tables: RankingTableConfig[];
  selected: string;
  onSelect: (slug: string) => void;
}

export function RankingTableSelector({
  tables,
  selected,
  onSelect,
}: RankingTableSelectorProps) {
  return (
    <div className="flex flex-wrap justify-center gap-1.5">
      {tables.map((table) => (
        <button
          key={table.slug}
          onClick={() => onSelect(table.slug)}
          className={cn(
            "px-3 py-1.5 rounded-md text-body font-medium whitespace-nowrap transition-colors",
            selected === table.slug
              ? "bg-primary text-primary-foreground"
              : "bg-secondary text-foreground hover:bg-secondary/80",
          )}
        >
          {table.display_name}
        </button>
      ))}
    </div>
  );
}
