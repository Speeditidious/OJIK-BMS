"use client";

import { cn } from "@/lib/utils";
import type { RankingType } from "@/lib/ranking-types";

interface RankingTypeToggleProps {
  type: RankingType;
  onToggle: (type: RankingType) => void;
}

const LABELS: Record<RankingType, string> = {
  exp: "경험치",
  bmsforce: "BMSFORCE",
};

export function RankingTypeToggle({ type, onToggle }: RankingTypeToggleProps) {
  return (
    <div className="inline-flex rounded-lg border border-border bg-secondary p-0.5 gap-0.5">
      {(["bmsforce", "exp"] as RankingType[]).map((t) => (
        <button
          key={t}
          onClick={() => onToggle(t)}
          className={cn(
            "inline-flex items-center justify-center px-4 py-1.5 rounded-md text-body font-medium transition-colors",
            type === t
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {LABELS[t]}
        </button>
      ))}
    </div>
  );
}
