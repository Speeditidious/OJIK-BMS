"use client";

import { Info, Music2, Clock, Hammer } from "lucide-react";
import { useTranslation } from "react-i18next";
import { formatDuration } from "@/lib/time";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { usePlaySummary, ClientTypeFilter } from "@/hooks/use-analysis";
import { cn } from "@/lib/utils";

const CLIENT_OPTIONS: { value: ClientTypeFilter }[] = [
  { value: "all" },
  { value: "lr2" },
  { value: "beatoraja" },
];

function StatCard({
  title,
  value,
  sub,
  icon: Icon,
  tooltip,
}: {
  title: string;
  value: string | number;
  sub: string;
  icon: React.ElementType;
  tooltip?: string;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="flex items-center gap-1">
          <CardTitle className="text-body font-medium">{title}</CardTitle>
          {tooltip && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Info className="h-3 w-3 text-muted-foreground cursor-help" />
              </TooltipTrigger>
              <TooltipContent className="max-w-xs text-label">
                {tooltip}
              </TooltipContent>
            </Tooltip>
          )}
        </div>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-stat font-bold">{value}</div>
        <p className="text-label text-muted-foreground">{sub}</p>
      </CardContent>
    </Card>
  );
}

interface StatsGridProps {
  clientType: ClientTypeFilter;
  onClientTypeChange: (ct: ClientTypeFilter) => void;
  userId?: string;
}

export function StatsGrid({ clientType, onClientTypeChange, userId }: StatsGridProps) {
  const { t } = useTranslation();
  const { data, isLoading, isError } = usePlaySummary(clientType, userId);

  const lastSync = data?.last_synced_at
    ? new Date(data.last_synced_at).toLocaleDateString()
    : t("dashboard.stats.noValue");

  return (
    <div className="mb-8">
      {/* Client type selector */}
      <div className="flex items-center gap-1 mb-3">
        {CLIENT_OPTIONS.map((opt) => (
          <Button
            key={opt.value}
            variant="ghost"
            size="sm"
            className={cn(
              "h-7 px-3 text-label rounded-full",
              clientType === opt.value
                ? "bg-primary/15 text-primary font-semibold"
                : "text-muted-foreground"
            )}
            onClick={() => onClientTypeChange(opt.value)}
          >
            {opt.value === "all" ? t("dashboard.stats.allClients") : opt.value === "lr2" ? "LR2" : "Beatoraja"}
          </Button>
        ))}
      </div>

      {/* Stat cards */}
      <TooltipProvider>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {isLoading ? (
          [0, 1, 2].map((i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <div className="h-4 w-24 bg-muted rounded animate-pulse" />
              </CardHeader>
              <CardContent>
                <div className="h-8 w-16 bg-muted rounded animate-pulse mb-1" />
                <div className="h-3 w-32 bg-muted rounded animate-pulse" />
              </CardContent>
            </Card>
          ))
        ) : isError || !data ? (
          <div className="col-span-3 flex items-center justify-center h-24 text-body text-muted-foreground">
            {t("common.states.loadFailed")}
          </div>
        ) : (
          <>
            <StatCard
              title={t("dashboard.stats.totalPlays")}
              value={data.total_play_count.toLocaleString()}
              sub={lastSync}
              icon={Music2}
            />
            <StatCard
              title={t("dashboard.stats.totalPlayTime")}
              value={formatDuration(data.total_playtime, t)}
              sub=""
              icon={Clock}
            />
            <StatCard
              title={t("dashboard.stats.totalNotes")}
              value={data.total_notes_hit.toLocaleString()}
              sub=""
              icon={Hammer}
            />
          </>
        )}
      </div>
      </TooltipProvider>
    </div>
  );
}
