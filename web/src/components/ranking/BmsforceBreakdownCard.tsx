"use client";

import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { BmsforceBreakdown } from "@/lib/ranking-types";

function formatSigned(value: number): string {
  if (Math.abs(value) < 1e-9) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(3)}`;
}

interface BmsforceBreakdownCardProps {
  breakdown: BmsforceBreakdown;
}

export function BmsforceBreakdownCard({
  breakdown,
}: BmsforceBreakdownCardProps) {
  const { t } = useTranslation();

  return (
    <Card className="mx-auto w-full max-w-sm border-border/60 bg-secondary/10">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{t("ranking.bmsforceBreakdown.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2.5 text-body">
        <div className="flex items-center justify-between gap-3">
          <span className="text-muted-foreground">{t("ranking.bmsforceBreakdown.ratingContribution")}</span>
          <span className="font-semibold tabular-nums">{formatSigned(breakdown.rating_component)}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-muted-foreground">{t("ranking.bmsforceBreakdown.levelContribution")}</span>
          <span className="font-semibold tabular-nums">{formatSigned(breakdown.level_component)}</span>
        </div>
        <div className="flex items-center justify-between gap-3 border-t border-border/50 pt-2.5">
          <span className="font-medium">{t("ranking.bmsforceBreakdown.total")}</span>
          <span className="font-semibold tabular-nums">{formatSigned(breakdown.total)}</span>
        </div>
        <p className="text-caption text-muted-foreground leading-snug">
          {t("ranking.bmsforceBreakdown.roundingNote")}
        </p>
      </CardContent>
    </Card>
  );
}
