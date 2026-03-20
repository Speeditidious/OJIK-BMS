"use client";

import { Trophy } from "lucide-react";
import { useDanBadges, DanBadge } from "@/hooks/use-badges";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

// Map internal clear_type (0–9) to CSS variable label
const CLEAR_VAR: Record<number, string> = {
  0: "no-play",
  1: "failed",
  2: "assist",
  3: "easy",
  4: "normal",
  5: "hard",
  6: "exhard",
  7: "fc",
  8: "perfect",
  9: "max",
};

const CLEAR_LABELS: Record<number, string> = {
  0: "NO PLAY",
  1: "FAILED",
  2: "ASSIST",
  3: "EASY",
  4: "NORMAL",
  5: "HARD",
  6: "EX HARD",
  7: "FULL COMBO",
  8: "PERFECT",
  9: "MAX",
};

const CLIENT_ABBR: Record<string, string> = {
  lr2: "LR2",
  beatoraja: "BT",
};

function BadgeChip({ badge }: { badge: DanBadge }) {
  const varName = CLEAR_VAR[badge.clear_type] ?? "no-play";
  const label = CLEAR_LABELS[badge.clear_type] ?? String(badge.clear_type);
  const clientAbbr = CLIENT_ABBR[badge.client_type] ?? badge.client_type.toUpperCase();

  return (
    <div
      className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 border text-xs font-medium"
      style={{
        borderColor: `hsl(var(--clear-${varName})/0.6)`,
        background: `hsl(var(--clear-${varName})/0.15)`,
        color: `hsl(var(--clear-${varName}))`,
      }}
    >
      <Trophy className="h-3 w-3 shrink-0" />
      <span>{badge.short_name ?? badge.name}</span>
      <span
        className="rounded px-1 py-0 text-[9px] font-bold"
        style={{ background: `hsl(var(--clear-${varName})/0.25)` }}
      >
        {label}
      </span>
      <span className="text-[9px] opacity-60">{clientAbbr}</span>
    </div>
  );
}

export function DanBadgeShowcase() {
  const { data: badges, isLoading } = useDanBadges();

  const groups: Record<string, DanBadge[]> = {};
  if (badges) {
    for (const badge of badges) {
      const key = badge.category ?? "미분류";
      if (!groups[key]) groups[key] = [];
      groups[key].push(badge);
    }
  }
  const categoryKeys = Object.keys(groups);

  return (
    <Card>
      <CardHeader>
        <CardTitle>단위인정 배지</CardTitle>
        <CardDescription>관리자가 지정한 단위인정 코스를 클리어하면 배지가 표시됩니다.</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="flex gap-2 flex-wrap">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-8 w-28 bg-muted rounded-full animate-pulse" />
            ))}
          </div>
        )}
        {!isLoading && categoryKeys.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-8">
            단위인정 코스를 클리어하면 배지가 표시됩니다.
          </p>
        )}
        {!isLoading && categoryKeys.length > 0 && (
          <div className="space-y-4">
            {categoryKeys.map((cat) => (
              <div key={cat}>
                <p className="text-xs font-semibold text-muted-foreground mb-2">{cat}</p>
                <div className="flex flex-wrap gap-2">
                  {groups[cat].map((badge) => (
                    <BadgeChip key={`${badge.dan_course_id}-${badge.client_type}`} badge={badge} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
