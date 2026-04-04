"use client";

import { Info, Music2, Clock, Hammer } from "lucide-react";
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

function formatPlaytime(seconds: number): string {
  if (!seconds) return "0시간";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h >= 100) return `${h.toLocaleString()}시간`;
  if (h > 0) return m > 0 ? `${h}시간 ${m}분` : `${h}시간`;
  return `${m}분`;
}

const CLIENT_OPTIONS: { label: string; value: ClientTypeFilter }[] = [
  { label: "통합", value: "all" },
  { label: "LR2", value: "lr2" },
  { label: "Beatoraja", value: "beatoraja" },
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
}

export function StatsGrid({ clientType, onClientTypeChange }: StatsGridProps) {
  const { data, isLoading, isError } = usePlaySummary(clientType);

  const lastSync = data?.last_synced_at
    ? new Date(data.last_synced_at).toLocaleDateString("ko-KR")
    : "없음";

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
            {opt.label}
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
            데이터를 불러오지 못했습니다
          </div>
        ) : (
          <>
            <StatCard
              title="총 플레이 수"
              value={data.total_play_count.toLocaleString()}
              sub={`최근 동기화: ${lastSync}`}
              icon={Music2}
            />
            <StatCard
              title="총 플레이 시간"
              value={formatPlaytime(data.total_playtime)}
              sub="전체 플레이 누적 시간"
              icon={Clock}
            />
            <StatCard
              title="총 격파한 노트 수"
              value={data.total_notes_hit.toLocaleString()}
              sub="누적 판정 합계"
              icon={Hammer}
            />
          </>
        )}
      </div>
      </TooltipProvider>
    </div>
  );
}
