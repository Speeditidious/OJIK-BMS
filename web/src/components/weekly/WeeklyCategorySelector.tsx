"use client";

import { cn } from "@/lib/utils";
import type { CategoryMeta } from "@/lib/weekly-types";

interface Props {
  categories: CategoryMeta[];
  selected: string;
  onSelect: (categoryKey: string) => void;
}

export function WeeklyCategorySelector({ categories, selected, onSelect }: Props) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2">
      {categories.map((c) => (
        <button
          key={c.key}
          onClick={() => onSelect(c.key)}
          className={cn(
            "px-5 py-2 rounded-xl text-base font-semibold transition-colors",
            c.key === selected
              ? "bg-primary text-primary-foreground shadow-md"
              : "bg-secondary hover:bg-secondary/80",
          )}
        >
          {c.name}
        </button>
      ))}
    </div>
  );
}
