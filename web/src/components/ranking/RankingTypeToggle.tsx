"use client";

import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import type { RankingType } from "@/lib/ranking-types";

interface RankingTypeToggleProps {
  type: RankingType;
  onToggle: (type: RankingType) => void;
}

export function RankingTypeToggle({ type, onToggle }: RankingTypeToggleProps) {
  const { t } = useTranslation();

  const LABELS: Record<RankingType, string> = {
    exp: t("ranking.type.exp"),
    bmsforce: t("ranking.type.bmsforce"),
  };

  return (
    <div className="inline-flex rounded-lg border border-border bg-secondary p-0.5 gap-0.5">
      {(["bmsforce", "exp"] as RankingType[]).map((rankType) => (
        <button
          key={rankType}
          onClick={() => onToggle(rankType)}
          className={cn(
            "inline-flex items-center justify-center px-4 py-1.5 rounded-md text-body font-medium transition-colors",
            type === rankType
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {LABELS[rankType]}
        </button>
      ))}
    </div>
  );
}
