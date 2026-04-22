"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  CalendarDays,
  ChevronLeft,
  Clock,
  Hammer,
  HelpCircle,
  LayoutDashboard,
  Music2,
  Sparkles,
  TrendingUp,
  Trophy,
} from "lucide-react";
import { Navbar } from "@/components/layout/navbar";
import { StatsGrid } from "@/components/dashboard/StatsGrid";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { ScoreUpdates } from "@/components/dashboard/ScoreUpdates";
import { TableClearSection } from "@/components/dashboard/TableClearSection";
import { DashboardUserHeader } from "@/components/dashboard/DashboardUserHeader";
import { ActivityHeatmap } from "@/components/charts/ActivityHeatmap";
import { ActivityBarChart, type ActivitySeries } from "@/components/charts/ActivityBarChart";
import { ActivityCalendar } from "@/components/charts/ActivityCalendar";
import { RatingDetailSection } from "@/components/ranking/RatingDetailSection";
import { RankingTableSelector } from "@/components/ranking/RankingTableSelector";
import { RatingChangeTabContent } from "@/components/ranking/RatingChangeTabContent";
import { ProfileActionBar } from "@/components/profile/ProfileActionBar";
import { DateRangePicker, type DateRangeValue } from "@/components/common/DateRangePicker";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useChartWidth } from "@/hooks/use-chart-size";
import {
  useActivityBar,
  useActivityHeatmap,
  useAggregatedRatingUpdates,
  useCourseActivity,
  usePlaySummary,
  useRecentUpdates,
  type ClientTypeFilter,
} from "@/hooks/use-analysis";
import { useUserProfile } from "@/hooks/use-user-profile";
import { useMyRank, useRankingHistory, useRankingTables } from "@/hooks/use-rankings";
import type {
  RatingContributionScope,
  RatingContributionSortBy,
  RatingHistoryMetric,
} from "@/lib/ranking-types";
import { cn } from "@/lib/utils";
import { formatRatingMetric, formatCompactNumber } from "@/lib/rating-format";
import { rangeFromPreset, daysInRange } from "@/lib/date-range";
import { ACTIVITY_CATEGORIES } from "@/lib/activity-categories";
import type { ScoreUpdatesViewMode } from "@/components/dashboard/ScoreUpdates";
import { pickTickResolution, formatTick, computeTicks } from "@/lib/axis-format";
import { useAuthStore } from "@/stores/auth";

function formatPlaytime(seconds: number): string {
  if (seconds <= 0) return "0분";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}시간 ${m}분`;
  return `${m}분`;
}

function buildCountMap(items?: Array<{ date: string; count: number }>): Record<string, number> {
  const map: Record<string, number> = {};
  for (const item of items ?? []) {
    map[item.date] = item.count;
  }
  return map;
}

function mergeActivityWithRating<T extends { date: string; rating_updates?: number }>(
  data: T[],
  ratingUpdates: Array<{ date: string; count: number }> | undefined,
): T[] {
  const ratingMap = buildCountMap(ratingUpdates);
  return data.map((item) => ({
    ...item,
    rating_updates: ratingMap[item.date] ?? 0,
  }));
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
  sub: string;
  icon: React.ElementType;
  uncertain?: boolean;
  uncertainTooltip?: string;
  valueClassName?: string;
  /** CSS variable for value color, e.g. "var(--warning)". Overrides valueClassName color. */
  accentVar?: string;
}) {
  const numericValue = parseFloat(value);
  const isZero = !isNaN(numericValue) && numericValue === 0;
  const valueStyle = accentVar && !isZero ? { color: `hsl(${accentVar})` } : undefined;

  return (
    <Card className="border-dashed">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 px-4 pb-1 pt-3">
        <p className="text-label font-medium">{title}</p>
        <Icon className="h-3.5 w-3.5 text-muted-foreground" />
      </CardHeader>
      <CardContent className="px-4 pb-3">
        <div className={cn("text-stat font-bold", isZero ? "text-muted-foreground" : valueClassName)} style={valueStyle}>
          {uncertain && uncertainTooltip ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="inline-flex cursor-help items-center gap-1 text-muted-foreground">
                  <span className="underline decoration-dashed underline-offset-2">-</span>
                  <HelpCircle className="h-3.5 w-3.5" />
                </span>
              </TooltipTrigger>
              <TooltipContent className="max-w-xs text-label">
                {uncertainTooltip}
              </TooltipContent>
            </Tooltip>
          ) : value}
        </div>
        <p className="text-caption text-muted-foreground">{sub}</p>
      </CardContent>
    </Card>
  );
}

type RatingHistoryMetricLocal = RatingHistoryMetric;

function RatingHistoryGraph({
  points,
  metric,
}: {
  points: Array<{ date: string; exp: number; rating: number; rating_norm: number }>;
  metric: RatingHistoryMetricLocal;
}) {
  const [chartRef, chartWidth] = useChartWidth(150);
  const color = metric === "exp"
    ? "hsl(var(--primary))"
    : metric === "rating"
      ? "hsl(var(--accent))"
      : "hsl(var(--clear-exhard))";
  const dataKey = metric === "exp" ? "exp" : metric === "rating" ? "rating" : "rating_norm" as const;

  if (points.length === 0) {
    return (
      <div className="flex h-56 items-center justify-center text-body text-muted-foreground">
        이 기간에 레이팅 변동 데이터가 없습니다.
      </div>
    );
  }

  if (chartWidth === 0) {
    return <div ref={chartRef} style={{ width: "100%", height: 220 }} />;
  }

  const dates = points.map((p) => p.date);
  const days = daysInRange({ from: dates[0], to: dates[dates.length - 1] });
  const resolution = pickTickResolution(days);
  const tickDates = computeTicks(dates, days);

  const values = points.map((p) => p[dataKey]);
  const dataMin = Math.min(...values);
  const dataMax = Math.max(...values);
  const pad = dataMax === dataMin
    ? (metric === "bmsforce" ? 0.01 : 1)
    : (dataMax - dataMin) * 0.1;

  const yDomain: [number | string, number | string] = points.length === 0
    ? [0, 1]
    : [dataMin - pad, dataMax + pad];

  const chartData = points.map((point) => ({
    ...point,
    label: point.date,
  }));

  return (
    <div ref={chartRef}>
      <AreaChart width={chartWidth} height={220} data={chartData} margin={{ top: 8, right: 48, left: -4, bottom: 0 }}>
        <defs>
          <linearGradient id={`rating-${metric}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.34} />
            <stop offset="100%" stopColor={color} stopOpacity={0.04} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="hsl(var(--border)/0.45)" vertical={false} />
        <XAxis
          dataKey="label"
          ticks={tickDates}
          tickFormatter={(v: string) => formatTick(v, resolution)}
          tick={{ fontSize: "var(--text-caption)", fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
          tickMargin={6}
          minTickGap={36}
          padding={{ left: 0, right: 8 }}
        />
        <YAxis
          domain={yDomain}
          tick={{ fontSize: "var(--text-caption)", fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={false}
          allowDecimals={metric === "bmsforce"}
          tickFormatter={(value: number) => {
            if (metric === "bmsforce") return formatRatingMetric("bmsforce", Number(value));
            return formatCompactNumber(Number(value));
          }}
        />
        <RechartsTooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const row = payload[0].payload as typeof chartData[number];
            return (
              <div className="rounded-lg border border-border bg-card px-3 py-2 text-label">
                <p className="font-medium">{row.date}</p>
                <p style={{ color }}>
                  {metric === "exp" ? "경험치" : metric === "rating" ? "레이팅" : "BMSFORCE"}: {
                    formatRatingMetric(
                      metric === "bmsforce" ? "bmsforce" : metric,
                      row[dataKey],
                    )
                  }
                </p>
              </div>
            );
          }}
        />
        <Area
          type="monotone"
          dataKey={dataKey}
          stroke={color}
          fill={`url(#rating-${metric})`}
          strokeWidth={2}
        />
      </AreaChart>
    </div>
  );
}

function CalendarDayDetail({
  userId,
  date,
  clientType,
  onBack,
  backLabel = "캘린더로 돌아가기",
  rankingTables,
  selectedRankingTable,
  onSelectRankingTable,
  dayView,
  onDayViewChange,
  ratingMetric,
  onRatingMetricChange,
}: {
  userId: string;
  date: string;
  clientType: ClientTypeFilter;
  onBack: () => void;
  backLabel?: string;
  rankingTables: Array<{
    slug: string;
    table_id: string;
    display_name: string;
    display_order: number;
    top_n: number;
    has_exp: boolean;
    has_rating: boolean;
    has_bmsforce: boolean;
    dan_decorations: string[];
  }>;
  selectedRankingTable: string | null;
  onSelectRankingTable: (slug: string) => void;
  dayView: ScoreUpdatesViewMode;
  onDayViewChange: (v: ScoreUpdatesViewMode) => void;
  ratingMetric: RatingHistoryMetric;
  onRatingMetricChange: (m: RatingHistoryMetric) => void;
}) {
  const { data } = useRecentUpdates(1, clientType, date, selectedRankingTable, userId);
  const aggregatedRatingDay = useAggregatedRatingUpdates({ date, userId });
  const autoSelectedDateRef = useRef<string | null>(null);
  const [y, m, d] = date.split("-").map(Number);
  const updatedTables = useMemo(
    () => [...(aggregatedRatingDay.data?.tables ?? [])].sort((left, right) => left.display_order - right.display_order),
    [aggregatedRatingDay.data?.tables],
  );

  useEffect(() => {
    if (autoSelectedDateRef.current !== date) {
      autoSelectedDateRef.current = null;
    }
  }, [date]);

  useEffect(() => {
    if (updatedTables.length === 0) return;
    if (autoSelectedDateRef.current === date) return;
    const selectedHasUpdates = updatedTables.some((table) => table.table_slug === selectedRankingTable && table.count > 0);
    if (selectedHasUpdates) {
      autoSelectedDateRef.current = date;
      return;
    }
    onSelectRankingTable(updatedTables[0].table_slug);
    autoSelectedDateRef.current = date;
  }, [date, onSelectRankingTable, selectedRankingTable, updatedTables]);

  return (
    <div className="space-y-4">
      <Button
        variant="ghost"
        size="sm"
        className="-ml-1 gap-1.5 text-muted-foreground hover:text-foreground"
        onClick={onBack}
      >
        <ChevronLeft className="h-4 w-4" />
        {backLabel}
      </Button>
      <div className="flex items-center gap-2">
        <CalendarDays className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-bold">{y}년 {m}월 {d}일의 기록</h2>
      </div>

      {data?.day_summary && (
        <TooltipProvider>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
            <DayStatCard
              title="갱신 기록"
              value={`${data.day_summary.total_updates}`}
              sub="당일 기록 갱신 개수"
              icon={TrendingUp}
              accentVar="var(--warning)"
            />
            <DayStatCard
              title="신규 기록"
              value={`${data.day_summary.new_plays ?? 0}`}
              sub="당일 첫 플레이 기록 개수"
              icon={Sparkles}
              accentVar="var(--primary)"
            />
            <DayStatCard
              title="레이팅 갱신"
              value={`${aggregatedRatingDay.data?.count ?? 0}`}
              sub="당일 전체 난이도표 반영 개수"
              icon={Trophy}
              accentVar="var(--chart-rating)"
            />
            <DayStatCard
              title="플레이 수"
              value={`${data.day_summary.total_play_count ?? 0}`}
              sub="당일 플레이 횟수"
              icon={Music2}
              uncertain={data.day_summary.play_count_uncertain}
              uncertainTooltip="첫 동기화 당일 혹은 그 이전 기록의 플레이 횟수는 집계할 수 없습니다."
              accentVar="var(--chart-play)"
            />
            <DayStatCard
              title="플레이 시간"
              value={formatPlaytime(data.day_summary.total_playtime)}
              sub="당일 플레이 시간"
              icon={Clock}
              uncertain={data.day_summary.playtime_uncertain}
              uncertainTooltip="첫 동기화 당일 혹은 그 이전 기록의 플레이 시간은 집계할 수 없습니다."
            />
            <DayStatCard
              title="격파 노트 수"
              value={`${data.day_summary.total_notes_hit.toLocaleString()}`}
              sub="당일 격파 노트"
              icon={Hammer}
              uncertain={data.day_summary.notes_hit_uncertain}
              uncertainTooltip="첫 동기화 당일 혹은 그 이전 기록의 격파 노트 수는 집계할 수 없습니다."
            />
          </div>
        </TooltipProvider>
      )}

      <ScoreUpdates
        userId={userId}
        clientType={clientType}
        date={date}
        ratingBadgeCount={aggregatedRatingDay.data?.count ?? 0}
        viewMode={dayView}
        onViewModeChange={onDayViewChange}
        ratingSlot={rankingTables.length > 0 ? (
          <RatingChangeTabContent
            userId={userId}
            date={date}
            tables={rankingTables}
            selectedTableSlug={selectedRankingTable}
            onSelectTable={onSelectRankingTable}
            aggregatedTables={updatedTables}
            enableMyRankFallback={true}
            metric={ratingMetric}
            onMetricChange={onRatingMetricChange}
          />
        ) : undefined}
      />
    </div>
  );
}

const CURRENT_YEAR = new Date().getFullYear();
const CURRENT_MONTH = new Date().getMonth() + 1;

function makeDefaultRange(days: number): DateRangeValue {
  const presets = { 7: "week", 30: "month", 90: "3month", 365: "year" } as const;
  const preset = (presets as Record<number, import("@/lib/date-range").RangePreset | undefined>)[days] ?? "month";
  return { preset, range: rangeFromPreset(preset === "custom" ? "month" : preset) };
}

export function UserDashboardContent({ userId }: { userId: string }) {
  const searchParams = useSearchParams();
  const router = useRouter();

  const currentUser = useAuthStore((state) => state.user);
  const isOwner = currentUser?.id === userId;

  const { data: profileUser, isLoading: profileLoading, error: profileError } = useUserProfile(userId);
  const { data: rankingTables = [], isLoading: rankingTablesLoading } = useRankingTables();

  const [clientType, setClientType] = useState<ClientTypeFilter>("all");
  const [heatmapYear, setHeatmapYear] = useState(CURRENT_YEAR);
  const [activityRange, setActivityRange] = useState<DateRangeValue>(() => makeDefaultRange(30));
  const [activityView, setActivityView] = useState<"updates" | "plays" | "new_plays" | "rating_updates">("updates");
  const [activitySeries, setActivitySeries] = useState<ActivitySeries[]>(["updates", "new_plays", "plays", "rating_updates"]);
  const [ratingHistoryMetric, setRatingHistoryMetric] = useState<RatingHistoryMetric>("bmsforce");
  const [ratingHistoryRange, setRatingHistoryRange] = useState<DateRangeValue>(() => makeDefaultRange(90));
  const [calYear, setCalYear] = useState(CURRENT_YEAR);
  const [calMonth, setCalMonth] = useState(CURRENT_MONTH);

  const currentTab = searchParams.get("tab") ?? "distribution";
  // Separated per-tab date params
  const activityDate = searchParams.get("activity_date");
  const calendarDate = searchParams.get("calendar_date");
  const selectedRankingTable = searchParams.get("ranking_table") ?? rankingTables[0]?.slug ?? null;
  const ratingScope = ((searchParams.get("rating_scope") as RatingContributionScope | null) ?? "top");
  const ratingSort = ((searchParams.get("rating_sort") as RatingContributionSortBy | null) ?? "value");
  const ratingDir = ((searchParams.get("rating_dir") as "asc" | "desc" | null) ?? "desc");
  // URL-controlled state for CalendarDayDetail tabs — preserved on navigation back from /songs/[hash]
  const dayView = (searchParams.get("day_view") as ScoreUpdatesViewMode | null) ?? "summary";
  const ratingMetricParam = (searchParams.get("rating_metric") as RatingHistoryMetric | null) ?? "rating";

  // Backward compatibility: migrate legacy ?date= param once on mount
  const didMigrateRef = useRef(false);
  useEffect(() => {
    if (didMigrateRef.current) return;
    const legacyDate = searchParams.get("date");
    if (!legacyDate) return;
    didMigrateRef.current = true;
    const params = new URLSearchParams(searchParams.toString());
    params.delete("date");
    const tab = searchParams.get("tab") ?? "activity";
    if (tab === "calendar") {
      params.set("calendar_date", legacyDate);
    } else {
      params.set("activity_date", legacyDate);
    }
    router.replace(`/users/${userId}/dashboard?${params.toString()}`, { scroll: false });
  }, [searchParams, router, userId]);

  // Compute activity bar mode from activityRange
  const activityBarMode = useMemo(() => {
    return { kind: "range" as const, from: activityRange.range.from, to: activityRange.range.to };
  }, [activityRange]);

  const { data: heatmapData, isLoading: heatmapLoading } = useActivityHeatmap(heatmapYear, clientType, userId);
  const { data: barData, isLoading: barLoading } = useActivityBar({
    mode: activityBarMode,
    clientType,
    userId,
  });
  const { data: summaryData } = usePlaySummary("all", userId);

  const { data: calHeatmapData } = useActivityHeatmap(calYear, clientType, userId);
  const { data: calLr2Data } = useActivityHeatmap(calYear, "lr2", userId);
  const { data: calBeatorajaData } = useActivityHeatmap(calYear, "beatoraja", userId);

  const { data: heatmapCourseData } = useCourseActivity(heatmapYear, undefined, clientType, undefined, userId);
  const { data: barCourseData } = useCourseActivity(undefined, undefined, clientType, undefined, userId);
  const { data: calCourseData } = useCourseActivity(calYear, undefined, clientType, undefined, userId);

  const heatmapRatingUpdates = useAggregatedRatingUpdates({ year: heatmapYear, userId });
  const barRatingUpdates = useAggregatedRatingUpdates({
    from: activityRange.range.from,
    to: activityRange.range.to,
    userId,
  });
  const calendarRatingUpdates = useAggregatedRatingUpdates({ year: calYear, userId });

  const myRank = useMyRank(selectedRankingTable, userId);
  const ratingHistory = useRankingHistory(
    selectedRankingTable,
    ratingHistoryRange.range.from,
    ratingHistoryRange.range.to,
    userId,
  );

  useEffect(() => {
    if (!searchParams.get("ranking_table") && rankingTables.length > 0) {
      const params = new URLSearchParams(searchParams.toString());
      params.set("ranking_table", rankingTables[0].slug);
      router.replace(`/users/${userId}/dashboard?${params.toString()}`, { scroll: false });
    }
  }, [rankingTables, router, searchParams, userId]);

  const firstSyncDates = useMemo(() => {
    const map = summaryData?.first_synced_by_client;
    if (!map) return undefined;
    return {
      lr2: map.lr2 ? map.lr2.slice(0, 10) : undefined,
      beatoraja: map.beatoraja ? map.beatoraja.slice(0, 10) : undefined,
    };
  }, [summaryData]);

  const heatmapWithRating = useMemo(
    () => mergeActivityWithRating(heatmapData?.data ?? [], heatmapRatingUpdates.data?.dates),
    [heatmapData?.data, heatmapRatingUpdates.data?.dates],
  );
  const barWithRating = useMemo(
    () => mergeActivityWithRating(barData?.data ?? [], barRatingUpdates.data?.dates),
    [barData?.data, barRatingUpdates.data?.dates],
  );

  const heatmapRatingMap = useMemo(
    () => buildCountMap(heatmapRatingUpdates.data?.dates),
    [heatmapRatingUpdates.data?.dates],
  );

  const replaceParams = useCallback((updates: Record<string, string | null>) => {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(updates)) {
      if (value === null || value === "") params.delete(key);
      else params.set(key, value);
    }
    router.replace(`/users/${userId}/dashboard?${params.toString()}`, { scroll: false });
  }, [router, searchParams, userId]);

  const updateParams = useCallback((updates: Record<string, string | null>) => {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(updates)) {
      if (value === null || value === "") params.delete(key);
      else params.set(key, value);
    }
    router.push(`/users/${userId}/dashboard?${params.toString()}`, { scroll: false });
  }, [router, searchParams, userId]);

  function handleTabChange(value: string) {
    replaceParams({ tab: value });
  }

  // Calendar tab day click — sets calendar_date only
  function handleDayClick(dateStr: string) {
    updateParams({ tab: "calendar", calendar_date: dateStr });
  }

  function handleBackToCalendar() {
    replaceParams({ tab: "calendar", calendar_date: null });
  }

  // Activity tab day click — sets activity_date only
  function handleActivityDayClick(dateStr: string) {
    updateParams({ tab: "activity", activity_date: dateStr });
  }

  function handleBackToActivity() {
    replaceParams({ tab: "activity", activity_date: null });
  }

  function toggleActivitySeries(series: ActivitySeries) {
    setActivitySeries((prev) => {
      const exists = prev.includes(series);
      if (exists) {
        if (prev.length === 1) return prev;
        return prev.filter((item) => item !== series);
      }
      return [...prev, series];
    });
  }

  if (profileLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (profileError || !profileUser) {
    return (
      <div className="min-h-screen bg-background">
        <Navbar />
        <main className="container mx-auto px-4 py-8">
          <p className="text-muted-foreground">해당 유저를 찾을 수 없습니다.</p>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container mx-auto space-y-6 px-4 py-8">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <LayoutDashboard className="h-7 w-7 text-primary" />
            <h1 className="text-3xl font-bold">대시보드</h1>
          </div>
          <ProfileActionBar isOwner={isOwner} />
        </div>

        <div>
          <DashboardUserHeader
            username={profileUser.username}
            avatarUrl={profileUser.avatar_url}
            userId={userId}
            createdAt={profileUser.created_at}
            lastSyncedAt={profileUser.last_synced_at}
          />
        </div>

        <StatsGrid userId={userId} clientType={clientType} onClientTypeChange={setClientType} />

        <Tabs value={currentTab} onValueChange={handleTabChange} className="space-y-4">
          <TabsList>
            <TabsTrigger value="distribution">클리어 분포</TabsTrigger>
            <TabsTrigger value="rating" disabled={rankingTablesLoading || rankingTables.length === 0}>레이팅 상세</TabsTrigger>
            <TabsTrigger value="activity">활동 요약</TabsTrigger>
            <TabsTrigger value="calendar">활동 캘린더</TabsTrigger>
          </TabsList>

          <TabsContent value="distribution">
            <Card>
              <CardHeader>
                <CardTitle>난이도표 클리어 분포</CardTitle>
                <CardDescription>
                  난이도표 레벨별 클리어 현황. 막대를 클릭하면 해당 레벨/클리어 타입으로 필터링됩니다.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <TableClearSection userId={userId} clientType={clientType !== "all" ? clientType : undefined} />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="rating">
            <RatingDetailSection
              profileUser={profileUser}
              tables={rankingTables}
              selectedTableSlug={selectedRankingTable}
              onSelectTable={(slug) => updateParams({ ranking_table: slug })}
              userId={userId}
              myRank={myRank.data}
              myRankLoading={myRank.isLoading}
              scope={ratingScope}
              onScopeChange={(scope) => updateParams({ rating_scope: scope })}
              sortBy={ratingSort}
              sortDir={ratingDir}
              onSortChange={(sortBy, sortDir) => updateParams({ rating_sort: sortBy, rating_dir: sortDir })}
            />
          </TabsContent>

          <TabsContent value="activity" className="space-y-4">
            {currentTab === "activity" && activityDate ? (
              <CalendarDayDetail
                userId={userId}
                date={activityDate}
                clientType={clientType}
                onBack={handleBackToActivity}
                backLabel="활동 요약으로 돌아가기"
                rankingTables={rankingTables}
                selectedRankingTable={selectedRankingTable}
                onSelectRankingTable={(slug) => updateParams({ ranking_table: slug })}
                dayView={dayView}
                onDayViewChange={(v) => replaceParams({ day_view: v })}
                ratingMetric={ratingMetricParam}
                onRatingMetricChange={(m) => replaceParams({ rating_metric: m })}
              />
            ) : (
              <>
                <Card>
                  <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <CardTitle>활동 히트맵</CardTitle>
                      <CardDescription>연도별 플레이, 갱신, 레이팅 반영 흐름을 한 눈에 확인하세요</CardDescription>
                    </div>
                    <div className="flex w-full flex-col gap-2 lg:w-auto lg:items-end">
                      <div className="flex flex-wrap gap-1 lg:justify-end">
                        {ACTIVITY_CATEGORIES.map((cat) => (
                          <Button
                            key={cat.key}
                            variant={activityView === cat.key ? "secondary" : "ghost"}
                            size="sm"
                            className="h-7 px-2 text-label"
                            onClick={() => setActivityView(cat.key)}
                          >
                            {cat.label}
                          </Button>
                        ))}
                      </div>
                      <div className="flex items-center gap-1 lg:justify-end">
                        <Button variant="ghost" size="sm" onClick={() => setHeatmapYear((year) => year - 1)}>‹</Button>
                        <span className="w-12 text-center text-body font-medium">{heatmapYear}</span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setHeatmapYear((year) => Math.min(year + 1, CURRENT_YEAR))}
                          disabled={heatmapYear >= CURRENT_YEAR}
                        >
                          ›
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {heatmapLoading ? (
                      <div className="h-24 animate-pulse rounded bg-muted">
                        <span className="sr-only">로딩 중</span>
                      </div>
                    ) : (
                      <ActivityHeatmap
                        data={heatmapWithRating}
                        year={heatmapYear}
                        firstSyncDates={firstSyncDates}
                        clientType={clientType}
                        courseData={heatmapCourseData ?? []}
                        viewMode={activityView}
                      />
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <CardTitle>활동 그래프</CardTitle>
                      <CardDescription>활동 추이를 확인하세요</CardDescription>
                    </div>
                    <div className="flex w-full flex-col gap-2 lg:w-auto lg:items-end">
                      <div className="flex flex-wrap gap-1 lg:justify-end">
                        {ACTIVITY_CATEGORIES.map((cat) => (
                          <Button
                            key={cat.key}
                            variant={activitySeries.includes(cat.key) ? "secondary" : "ghost"}
                            size="sm"
                            className="h-7 px-2 text-label"
                            onClick={() => toggleActivitySeries(cat.key)}
                          >
                            {cat.label}
                          </Button>
                        ))}
                      </div>
                      <DateRangePicker
                        value={activityRange}
                        onChange={setActivityRange}
                        maxDays={730}
                        className="lg:items-end"
                      />
                    </div>
                  </CardHeader>
                  <CardContent>
                    {barLoading ? (
                      <div className="h-48 animate-pulse rounded bg-muted">
                        <span className="sr-only">로딩 중</span>
                      </div>
                    ) : (
                      <ActivityBarChart
                        data={barWithRating}
                        firstSyncDates={firstSyncDates}
                        clientType={clientType}
                        courseData={barCourseData ?? []}
                        activeModes={activitySeries}
                        rangeFrom={activityRange.range.from}
                        rangeTo={activityRange.range.to}
                      />
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <CardTitle>레이팅 그래프</CardTitle>
                      <CardDescription>선택한 난이도표의 경험치 / 레이팅 / BMSFORCE 추이를 봅니다.</CardDescription>
                    </div>
                    <div className="flex w-full flex-col gap-2 lg:w-auto lg:items-end">
                      {rankingTables.length > 0 && (
                        <div className="w-full lg:w-auto">
                          <RankingTableSelector
                            tables={rankingTables}
                            selected={selectedRankingTable ?? rankingTables[0].slug}
                            onSelect={(slug) => updateParams({ ranking_table: slug })}
                          />
                        </div>
                      )}
                      <div className="flex flex-wrap gap-1 lg:justify-end">
                        {(["exp", "rating", "bmsforce"] as const).map((value) => (
                          <Button
                            key={value}
                            variant={ratingHistoryMetric === value ? "secondary" : "ghost"}
                            size="sm"
                            className="h-7 px-2 text-label"
                            onClick={() => setRatingHistoryMetric(value)}
                          >
                            {value === "exp" ? "경험치" : value === "rating" ? "레이팅" : "BMSFORCE"}
                          </Button>
                        ))}
                      </div>
                      <DateRangePicker
                        value={ratingHistoryRange}
                        onChange={setRatingHistoryRange}
                        maxDays={730}
                        className="lg:items-end"
                      />
                    </div>
                  </CardHeader>
                  <CardContent>
                    {selectedRankingTable ? (
                      <RatingHistoryGraph
                        points={ratingHistory.data?.points ?? []}
                        metric={ratingHistoryMetric}
                      />
                    ) : (
                      <div className="flex h-56 items-center justify-center text-body text-muted-foreground">
                        레이팅 그래프를 보려면 난이도표를 선택해주세요.
                      </div>
                    )}
                  </CardContent>
                </Card>

                <RecentActivity
                  clientType={clientType}
                  heatmapData={heatmapWithRating}
                  ratingUpdatesByDate={heatmapRatingMap}
                  firstSyncDates={firstSyncDates}
                  onDayClick={handleActivityDayClick}
                  emptyMessage={isOwner ? "동기화된 활동 내역이 없습니다." : "이 유저는 아직 공개된 활동 내역이 없습니다."}
                />
              </>
            )}
          </TabsContent>

          <TabsContent value="calendar" className="space-y-4">
            {calendarDate ? (
              <CalendarDayDetail
                userId={userId}
                date={calendarDate}
                clientType={clientType}
                onBack={handleBackToCalendar}
                backLabel="캘린더로 돌아가기"
                rankingTables={rankingTables}
                selectedRankingTable={selectedRankingTable}
                onSelectRankingTable={(slug) => updateParams({ ranking_table: slug })}
                dayView={dayView}
                onDayViewChange={(v) => replaceParams({ day_view: v })}
                ratingMetric={ratingMetricParam}
                onRatingMetricChange={(m) => replaceParams({ rating_metric: m })}
              />
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle>활동 캘린더</CardTitle>
                  <CardDescription>날짜를 클릭하면 해당 날의 기록과 레이팅 변동을 확인합니다.</CardDescription>
                </CardHeader>
                <CardContent>
                  <ActivityCalendar
                    data={calHeatmapData?.data ?? []}
                    year={calYear}
                    month={calMonth}
                    onDayClick={handleDayClick}
                    onMonthChange={(year, month) => {
                      setCalYear(year);
                      setCalMonth(month);
                    }}
                    firstSyncDates={firstSyncDates}
                    dataLr2={clientType === "all" ? calLr2Data?.data : undefined}
                    dataBeatoraja={clientType === "all" ? calBeatorajaData?.data : undefined}
                    courseData={calCourseData ?? []}
                    ratingUpdatesData={calendarRatingUpdates.data?.dates}
                  />
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
