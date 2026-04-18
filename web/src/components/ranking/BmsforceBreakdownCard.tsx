"use client";

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
  return (
    <Card className="mx-auto w-full max-w-sm border-border/60 bg-secondary/10">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">BMSFORCE 기여 항목</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2.5 text-body">
        <div className="flex items-center justify-between gap-3">
          <span className="text-muted-foreground">레이팅 상승 기여</span>
          <span className="font-semibold tabular-nums">{formatSigned(breakdown.rating_component)}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-muted-foreground">레벨 상승 기여</span>
          <span className="font-semibold tabular-nums">{formatSigned(breakdown.level_component)}</span>
        </div>
        <div className="flex items-center justify-between gap-3 border-t border-border/50 pt-2.5">
          <span className="font-medium">합계</span>
          <span className="font-semibold tabular-nums">{formatSigned(breakdown.total)}</span>
        </div>
      </CardContent>
    </Card>
  );
}
