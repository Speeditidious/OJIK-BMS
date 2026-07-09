"use client";

import { useTranslation } from "react-i18next";
import { Clock, Hammer, HelpCircle, Music2, Sparkles, TrendingUp, Trophy } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { formatDuration } from "@/lib/time";

export interface DaySummaryData {
  total_updates: number;
  new_plays?: number | null;
  rating_updates?: number | null;
  total_play_count?: number | null;
  total_playtime?: number | null;
  total_notes_hit?: number | null;
  player_stats_unreliable?: boolean;
  play_count_uncertain?: boolean;
  play_count_uncertain_reason?: "first_sync" | "unsynced_date" | string | null;
  playtime_uncertain?: boolean;
  notes_hit_uncertain?: boolean;
}

function DayStatCard({
  title,
  value,
  sub,
  icon: Icon,
  uncertain,
  uncertainTooltip,
  valueClassName,
  accentVar,
}: {
  title: string;
  value: string;
  sub?: string;
  icon: React.ElementType;
  uncertain?: boolean;
  uncertainTooltip?: string;
  valueClassName?: string;
  accentVar?: string;
}) {
  const numericValue = parseFloat(value);
  const isZero = !isNaN(numericValue) && numericValue === 0;
  const valueStyle = accentVar && !isZero ? { color: `hsl(${accentVar})` } : undefined;

  return (
    <Card className="border border-border/60 shadow-none">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 px-[17px] pb-2 pt-[15px]">
        <p className="text-[13px] font-semibold text-muted-foreground">{title}</p>
        <Icon className="h-3.5 w-3.5 text-muted-foreground/50" />
      </CardHeader>
      <CardContent className="px-[17px] pb-[15px]">
        <div
          className={cn("text-[26px] font-extrabold leading-tight tabular-nums", isZero ? "text-muted-foreground" : valueClassName)}
          style={valueStyle}
        >
          {uncertain && uncertainTooltip ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="inline-flex cursor-help items-center gap-1 text-muted-foreground">
                  <span className="underline decoration-dashed underline-offset-2">-</span>
                  <HelpCircle className="h-3.5 w-3.5" />
                </span>
              </TooltipTrigger>
              <TooltipContent className="max-w-xs text-label">{uncertainTooltip}</TooltipContent>
            </Tooltip>
          ) : (
            value
          )}
        </div>
        {sub && <p className="text-caption text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}

interface DayStatGridProps {
  daySummary: DaySummaryData;
  className?: string;
}

export function DayStatGrid({ daySummary, className }: DayStatGridProps) {
  const { t } = useTranslation();
  const playCountUncertainTooltip =
    daySummary.play_count_uncertain_reason === "unsynced_date"
      ? t("dashboard.dayDetail.playCountUnsyncedDate")
      : t("dashboard.dayDetail.playCountUncertain");

  return (
    <TooltipProvider>
      <div className={cn("grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6", className)}>
        <DayStatCard
          title={t("dashboard.dayDetail.updates")}
          value={`${daySummary.total_updates}`}
          icon={TrendingUp}
          accentVar="var(--warning)"
        />
        <DayStatCard
          title={t("dashboard.dayDetail.newPlays")}
          value={`${daySummary.new_plays ?? 0}`}
          icon={Sparkles}
          accentVar="var(--primary)"
        />
        <DayStatCard
          title={t("dashboard.dayDetail.ratingUpdates")}
          value={`${daySummary.rating_updates ?? 0}`}
          icon={Trophy}
          accentVar="var(--chart-rating)"
        />
        <DayStatCard
          title={t("dashboard.dayDetail.playCount")}
          value={`${daySummary.total_play_count ?? 0}`}
          icon={Music2}
          uncertain={daySummary.player_stats_unreliable || daySummary.play_count_uncertain}
          uncertainTooltip={
            daySummary.player_stats_unreliable
              ? t("dashboard.dayDetail.playerStatsUnreliable")
              : playCountUncertainTooltip
          }
          accentVar="var(--chart-play)"
        />
        <DayStatCard
          title={t("dashboard.dayDetail.playTime")}
          value={formatDuration(daySummary.total_playtime ?? 0, t)}
          icon={Clock}
          uncertain={daySummary.player_stats_unreliable || daySummary.playtime_uncertain}
          uncertainTooltip={
            daySummary.player_stats_unreliable
              ? t("dashboard.dayDetail.playerStatsUnreliable")
              : t("dashboard.dayDetail.playTimeUncertain")
          }
        />
        <DayStatCard
          title={t("dashboard.dayDetail.notesHit")}
          value={`${(daySummary.total_notes_hit ?? 0).toLocaleString()}`}
          icon={Hammer}
          uncertain={daySummary.player_stats_unreliable || daySummary.notes_hit_uncertain}
          uncertainTooltip={
            daySummary.player_stats_unreliable
              ? t("dashboard.dayDetail.playerStatsUnreliable")
              : t("dashboard.dayDetail.notesHitUncertain")
          }
        />
      </div>
    </TooltipProvider>
  );
}
