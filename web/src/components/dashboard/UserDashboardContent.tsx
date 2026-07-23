"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslation } from "react-i18next";
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
  LayoutDashboard,
} from "lucide-react";
import { Navbar } from "@/components/layout/navbar";
import { StatsGrid } from "@/components/dashboard/StatsGrid";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { ScoreUpdates } from "@/components/dashboard/ScoreUpdates";
import { DayStatGrid } from "@/components/dashboard/DayStatGrid";
import { DayStatSheet } from "@/components/dashboard/DayStatSheet";
import { TableClearSection } from "@/components/dashboard/TableClearSection";
import { DashboardUserHeader } from "@/components/dashboard/DashboardUserHeader";
import { GoalsPanel } from "@/components/goals/GoalsPanel";
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
import { useChartWidth } from "@/hooks/use-chart-size";
import {
  useActivityBar,
  useActivityHeatmap,
  useCourseActivity,
  usePlaySummary,
  useRatingUpdateStatus,
  useRecentUpdates,
  useScoreUpdates,
  type ClientTypeFilter,
} from "@/hooks/use-analysis";
import { useUserProfile } from "@/hooks/use-user-profile";
import { useMyRank, useRankingHistory, useRankingTables } from "@/hooks/use-rankings";
import type {
  RatingContributionScope,
  RatingContributionSortBy,
  RatingHistoryMetric,
} from "@/lib/ranking-types";
import type { ClearVisibilitySource } from "@/hooks/use-dashboard-clear-visibility";
import { formatRatingMetric, formatCompactNumber } from "@/lib/rating-format";
import { rangeFromPreset, daysInRange } from "@/lib/date-range";
import { ACTIVITY_CATEGORIES } from "@/lib/activity-categories";
import type { ScoreUpdatesViewMode } from "@/components/dashboard/ScoreUpdates";
import { pickTickResolution, formatTick, computeTicks } from "@/lib/axis-format";
import { niceTicks, decimalsForStep } from "@/lib/axis-ticks";
import { buildDashboardUrl, getDashboardRankingTable, mergeDashboardParams } from "@/lib/dashboard-url-state.mjs";
import { useAuthStore } from "@/stores/auth";
import { useMonthDayNotes } from "@/hooks/use-day-notes";
import { DayNotePopover } from "@/components/fumen/DayNotePopover";
import { getInitialBrowserSearch } from "@/lib/static-route";

type RatingHistoryMetricLocal = RatingHistoryMetric;

function RatingHistoryGraph({
  points,
  metric,
  loading = false,
  active = true,
}: {
  points: Array<{ date: string; exp: number; rating: number; rating_norm: number }>;
  metric: RatingHistoryMetricLocal;
  loading?: boolean;
  active?: boolean;
}) {
  const { t } = useTranslation();
  const [chartRef, chartWidth] = useChartWidth(150, {
    active,
    remeasureKey: `${metric}:${points.length}:${points[0]?.date ?? ""}:${points[points.length - 1]?.date ?? ""}`,
  });
  const color = metric === "exp"
    ? "hsl(var(--primary))"
    : metric === "rating"
      ? "hsl(var(--accent))"
      : "hsl(var(--clear-exhard))";
  const dataKey = metric === "exp" ? "exp" : metric === "rating" ? "rating" : "rating_norm" as const;

  if (loading) {
    return (
      <div className="space-y-3">
        <div className="h-4 w-28 animate-pulse rounded bg-muted" />
        <div className="h-[300px] animate-pulse rounded-lg bg-muted" />
        <p className="text-caption text-muted-foreground">Loading rating history data...</p>
      </div>
    );
  }

  if (points.length === 0) {
    return (
      <div className="flex h-[300px] items-center justify-center text-body text-muted-foreground">
        No rating change data for this period.
      </div>
    );
  }

  if (chartWidth === 0) {
    return (
      <div
        ref={chartRef}
        className="flex h-[300px] w-full items-center justify-center rounded-lg border border-dashed border-border bg-muted/20 px-6 text-center"
      >
        <div className="space-y-2">
          <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-primary" />
          <p className="text-body font-medium text-foreground">Preparing rating graph layout...</p>
          <p className="text-caption text-muted-foreground">
            The graph will render once the tab layout stabilizes.
          </p>
        </div>
      </div>
    );
  }

  const dates = points.map((p) => p.date);
  const days = daysInRange({ from: dates[0], to: dates[dates.length - 1] });
  const resolution = pickTickResolution(days);
  const tickDates = computeTicks(dates, days);

  const values = points.map((p) => p[dataKey]);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const flat = rawMin === rawMax;
  const fallbackPad = metric === "bmsforce" ? 0.01 : 1;
  const yDomainMin = flat ? rawMin - fallbackPad : rawMin;
  const yDomainMax = flat ? rawMax + fallbackPad : rawMax;
  const yDomain: [number, number] = [yDomainMin, yDomainMax];
  const { ticks: yTickValues, step: yStep } = flat
    ? { ticks: undefined as undefined, step: 0 }
    : niceTicks(yDomainMin, yDomainMax, 8);
  const yDecimals = decimalsForStep(yStep);

  const chartData = points.map((point) => ({
    ...point,
    label: point.date,
  }));

  return (
    <div ref={chartRef}>
      <AreaChart width={chartWidth} height={300} data={chartData} margin={{ top: 8, right: 48, left: -4, bottom: 0 }}>
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
          tickFormatter={(v: string) => formatTick(v, resolution, t)}
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
          ticks={yTickValues}
          tick={{ fontSize: "var(--text-caption)", fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={false}
          allowDecimals={metric === "bmsforce" || yStep < 1}
          tickFormatter={(value: number) => {
            const n = Number(value);
            if (yStep < 1) return n.toFixed(yDecimals);
            return formatCompactNumber(Math.round(n));
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
                  {metric === "exp" ? "EXP" : metric === "rating" ? "Rating" : "BMSFORCE"}: {
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

function CalendarDayDetailSkeleton({ backLabel, dateLabel }: { backLabel: string; dateLabel: string }) {
  return (
    <div className="space-y-4">
      <Button
        variant="ghost"
        size="sm"
        className="-ml-1 gap-1.5 text-muted-foreground hover:text-foreground"
        disabled
      >
        <ChevronLeft className="h-4 w-4" />
        {backLabel}
      </Button>
      <div className="flex items-center gap-2">
        <CalendarDays className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-bold">{dateLabel}</h2>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        {Array.from({ length: 6 }).map((_, index) => (
          <Card key={index} className="border-dashed">
            <CardHeader className="space-y-2 px-4 pb-1 pt-3">
              <div className="h-3 w-16 animate-pulse rounded bg-muted" />
              <div className="h-6 w-12 animate-pulse rounded bg-muted" />
            </CardHeader>
            <CardContent className="px-4 pb-3">
              <div className="h-3 w-20 animate-pulse rounded bg-muted" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader className="pb-2">
          <div className="h-6 w-24 animate-pulse rounded bg-muted" />
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="mx-auto flex w-fit gap-2 rounded-lg border border-border/60 p-1">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="h-8 w-24 animate-pulse rounded bg-muted" />
            ))}
          </div>
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="h-14 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function CalendarDayDetail({
  userId,
  date,
  clientType,
  onBack,
  backLabel,
  isOwner,
  hasNote,
  username,
  avatarUrl,
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
  isOwner: boolean;
  hasNote?: boolean;
  username: string;
  avatarUrl?: string | null;
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
  const { t } = useTranslation();
  const recentUpdates = useRecentUpdates(1, clientType, date, undefined, userId);
  const scoreUpdates = useScoreUpdates(clientType, date, 50, userId);
  const { data } = recentUpdates;
  const autoSelectedDateRef = useRef<string | null>(null);
  const [y, m, d] = date.split("-").map(Number);
  const updatedTables = useMemo(
    () => [...(data?.rating_update_tables ?? [])].sort((left, right) => left.display_order - right.display_order),
    [data?.rating_update_tables],
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

  const dateText = `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  const dateLabel = t("dashboard.dayDetail.title", { date: dateText });
  const resolvedBackLabel = backLabel ?? t("dashboard.calendar.back");
  const isDayDetailLoading =
    (recentUpdates.isLoading && !recentUpdates.data) ||
    (scoreUpdates.isLoading && !scoreUpdates.data);

  if (isDayDetailLoading) {
    return <CalendarDayDetailSkeleton backLabel={resolvedBackLabel} dateLabel={dateLabel} />;
  }

  return (
    <div className="space-y-4">
      <Button
        variant="ghost"
        size="sm"
        className="-ml-1 gap-1.5 text-muted-foreground hover:text-foreground"
        onClick={onBack}
      >
        <ChevronLeft className="h-4 w-4" />
        {resolvedBackLabel}
      </Button>
      <div className="flex items-center gap-2">
        <CalendarDays className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-bold">{dateLabel}</h2>
      </div>

      {data?.day_summary && (
        <DayStatGrid daySummary={data.day_summary} />
      )}

      <ScoreUpdates
        userId={userId}
        clientType={clientType}
        date={date}
        ratingBadgeCount={data?.day_summary?.rating_updates ?? 0}
        viewMode={dayView}
        onViewModeChange={onDayViewChange}
        noteSlot={
          <DayNotePopover userId={userId} date={date} isOwner={isOwner} hasNote={hasNote} />
        }
        daySheetSlot={
          <DayStatSheet
            userId={userId}
            date={date}
            clientType={clientType}
            isOwner={isOwner}
            username={username}
            avatarUrl={avatarUrl}
            rankingTables={rankingTables.map((t) => ({
              slug: t.slug,
              table_id: t.table_id,
              display_name: t.display_name,
              display_order: t.display_order,
              symbol: t.slug,
              has_bmsforce: t.has_bmsforce,
            }))}
            daySummary={data?.day_summary}
            scoreUpdatesData={scoreUpdates.data ?? null}
          />
        }
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
            enabled={dayView === "rating"}
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

function migrateInitialSearch(raw: string): { params: URLSearchParams; migratedSearch: string | null } {
  const params = new URLSearchParams(raw);
  const legacyDate = params.get("date");
  if (!legacyDate) return { params, migratedSearch: null };
  params.delete("date");
  const tab = params.get("tab") ?? "activity";
  params.set(tab === "calendar" ? "calendar_date" : "activity_date", legacyDate);
  return { params, migratedSearch: params.toString() };
}

export function UserDashboardContent({ userId }: { userId: string }) {
  const { t } = useTranslation();
  const routeSearchParams = useSearchParams();
  const [searchParams, setSearchParams] = useState(() => {
    const raw = getInitialBrowserSearch() || routeSearchParams.toString();
    return migrateInitialSearch(raw).params;
  });
  const [initialMigratedSearch] = useState(() => {
    const raw = getInitialBrowserSearch() || routeSearchParams.toString();
    return migrateInitialSearch(raw).migratedSearch;
  });
  const routeSearchStr = routeSearchParams.toString();
  const [prevRouteSearch, setPrevRouteSearch] = useState(routeSearchStr);
  if (prevRouteSearch !== routeSearchStr) {
    setPrevRouteSearch(routeSearchStr);
    setSearchParams(new URLSearchParams(window.location.search));
  }

  const { user: currentUser, isInitialized: authInitialized } = useAuthStore();
  const isOwner = currentUser?.id === userId;

  const cvParam = (searchParams.get("cv") as "mine" | null) ?? null;
  const clearVisibilitySource: ClearVisibilitySource =
    isOwner || (cvParam === "mine" && !!currentUser) ? "viewer" : "target";

  const { data: profileUser, isLoading: profileLoading, error: profileError } = useUserProfile(userId);
  const { data: rankingTables = [], isLoading: rankingTablesLoading } = useRankingTables();

  useEffect(() => {
    const syncSearchParams = () => {
      setSearchParams(new URLSearchParams(window.location.search));
    };
    window.addEventListener("popstate", syncSearchParams);
    return () => window.removeEventListener("popstate", syncSearchParams);
  }, []);

  useEffect(() => {
    if (initialMigratedSearch === null) return;
    window.history.replaceState(
      window.history.state,
      "",
      initialMigratedSearch ? `${window.location.pathname}?${initialMigratedSearch}` : window.location.pathname,
    );
  }, [initialMigratedSearch]);

  const [clientType, setClientType] = useState<ClientTypeFilter>("all");
  const [heatmapYear, setHeatmapYear] = useState(CURRENT_YEAR);
  const [activityRange, setActivityRange] = useState<DateRangeValue>(() => makeDefaultRange(30));
  const [activityView, setActivityView] = useState<"updates" | "plays" | "new_plays" | "rating_updates">("updates");
  const [activitySeries, setActivitySeries] = useState<ActivitySeries[]>(["updates", "new_plays", "rating_updates", "plays"]);
  const [ratingHistoryMetric, setRatingHistoryMetric] = useState<RatingHistoryMetric>("bmsforce");
  const [ratingHistoryRange, setRatingHistoryRange] = useState<DateRangeValue>(() => makeDefaultRange(30));
  const [calYear, setCalYear] = useState(CURRENT_YEAR);
  const [calMonth, setCalMonth] = useState(CURRENT_MONTH);

  const currentTab = searchParams.get("tab") ?? "distribution";
  // Separated per-tab date params
  const activityDate = searchParams.get("activity_date");
  const calendarDate = searchParams.get("calendar_date");
  const selectedRankingTable = getDashboardRankingTable(searchParams, rankingTables[0]?.slug);
  const ratingScope = ((searchParams.get("rating_scope") as RatingContributionScope | null) ?? "top");
  const ratingSort = ((searchParams.get("rating_sort") as RatingContributionSortBy | null) ?? "value");
  const ratingDir = ((searchParams.get("rating_dir") as "asc" | "desc" | null) ?? "desc");
  // URL-controlled state for CalendarDayDetail tabs — preserved on navigation back from /songs/[hash]
  const dayView = (searchParams.get("day_view") as ScoreUpdatesViewMode | null) ?? "daySheet";
  const ratingMetricParam = (searchParams.get("rating_metric") as RatingHistoryMetric | null) ?? "rating";
  const showRatingOverview = currentTab === "rating";
  const showActivityOverview = currentTab === "activity" && !activityDate;
  const showCalendarOverview = currentTab === "calendar" && !calendarDate;
  const showAnyActivityOverview = showActivityOverview || showCalendarOverview;

  // Compute activity bar mode from activityRange
  const activityBarMode = useMemo(() => {
    return { kind: "range" as const, from: activityRange.range.from, to: activityRange.range.to };
  }, [activityRange]);

  const { data: heatmapData, isLoading: heatmapLoading } = useActivityHeatmap(
    heatmapYear,
    clientType,
    userId,
    showActivityOverview,
  );
  const { data: barData, isLoading: barLoading } = useActivityBar({
    mode: activityBarMode,
    clientType,
    userId,
    enabled: showActivityOverview,
  });
  const { data: summaryData } = usePlaySummary("all", userId, showAnyActivityOverview);

  const { data: calHeatmapData } = useActivityHeatmap(calYear, clientType, userId, showCalendarOverview);
  const { data: calLr2Data } = useActivityHeatmap(calYear, "lr2", userId, showCalendarOverview);
  const { data: calBeatorajaData } = useActivityHeatmap(calYear, "beatoraja", userId, showCalendarOverview);
  const calRatingStatus = useRatingUpdateStatus(
    `${calYear}-01-01`,
    `${calYear}-12-31`,
    userId,
    showCalendarOverview && Boolean(calHeatmapData?.rating_updates_pending),
  );

  const { data: monthNotes } = useMonthDayNotes(
    currentTab === "calendar" ? userId : null,
    calYear,
    calMonth,
  );
  const noteDatesSet = useMemo<Set<string>>(
    () => new Set((monthNotes ?? []).map((n) => n.date)),
    [monthNotes],
  );

  const { data: heatmapCourseData } = useCourseActivity(
    heatmapYear,
    undefined,
    clientType,
    undefined,
    userId,
    showActivityOverview,
  );
  const { data: barCourseData } = useCourseActivity(
    undefined,
    undefined,
    clientType,
    undefined,
    userId,
    showActivityOverview,
  );
  const { data: calCourseData } = useCourseActivity(
    calYear,
    undefined,
    clientType,
    undefined,
    userId,
    showCalendarOverview,
  );

  const myRank = useMyRank(selectedRankingTable, userId, showRatingOverview);
  const ratingHistory = useRankingHistory(
    selectedRankingTable,
    ratingHistoryRange.range.from,
    ratingHistoryRange.range.to,
    userId,
    showActivityOverview,
  );
  const isActivityRatingHistoryDataLoading =
    rankingTablesLoading ||
    (showActivityOverview && (ratingHistory.isLoading || (ratingHistory.isFetching && !ratingHistory.data)));

  const firstSyncDates = useMemo(() => {
    const map = summaryData?.first_synced_by_client;
    if (!map) return undefined;
    return {
      lr2: map.lr2 ? map.lr2.slice(0, 10) : undefined,
      beatoraja: map.beatoraja ? map.beatoraja.slice(0, 10) : undefined,
    };
  }, [summaryData]);

  const heatmapRatingMap = useMemo(
    () => Object.fromEntries((heatmapData?.data ?? []).map((item) => [item.date, item.rating_updates ?? 0])),
    [heatmapData?.data],
  );
  const calendarRatingUpdatesData = useMemo(() => {
    const statusRows = calRatingStatus.data?.pending === false ? calRatingStatus.data.data : null;
    return (statusRows ?? (calHeatmapData?.data ?? [])
      .filter((item) => (item.rating_updates ?? 0) > 0)
      .map((item) => ({ date: item.date, count: item.rating_updates ?? 0 })))
      .filter((item) => item.count > 0);
  }, [calHeatmapData?.data, calRatingStatus.data]);
  const calendarRatingUpdatesPending =
    Boolean(calHeatmapData?.rating_updates_pending) && calRatingStatus.data?.pending !== false;

  const replaceParams = useCallback((updates: Record<string, string | null>) => {
    const params = mergeDashboardParams(searchParams, updates);
    const nextUrl = buildDashboardUrl(window.location.pathname, searchParams, updates);
    window.history.replaceState(window.history.state, "", nextUrl);
    setSearchParams(params);
  }, [searchParams]);

  const updateParams = useCallback((updates: Record<string, string | null>) => {
    const params = mergeDashboardParams(searchParams, updates);
    const nextUrl = buildDashboardUrl(window.location.pathname, searchParams, updates);
    window.history.pushState(window.history.state, "", nextUrl);
    setSearchParams(params);
  }, [searchParams]);

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
          <p className="text-muted-foreground">{t("common.states.notFound")}</p>
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
            <h1 className="text-3xl font-bold">{t("common.nav.dashboard")}</h1>
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
            isOwner={isOwner}
          />
        </div>

        <StatsGrid userId={userId} clientType={clientType} onClientTypeChange={setClientType} />

        <Tabs value={currentTab} onValueChange={handleTabChange} className="space-y-4">
          <TabsList>
            <TabsTrigger value="distribution">{t("dashboard.tabs.distribution")}</TabsTrigger>
            <TabsTrigger value="rating" disabled={rankingTablesLoading || rankingTables.length === 0}>{t("dashboard.tabs.rating")}</TabsTrigger>
            <TabsTrigger value="activity">{t("dashboard.tabs.activity")}</TabsTrigger>
            <TabsTrigger value="calendar">{t("dashboard.tabs.calendar")}</TabsTrigger>
            {isOwner && <TabsTrigger value="goals">{t("dashboard.tabs.goals")}</TabsTrigger>}
          </TabsList>

          <TabsContent value="distribution">
            <Card>
              <CardHeader>
                <CardTitle>{t("dashboard.distribution.title")}</CardTitle>
                <CardDescription>
                  {t("dashboard.distribution.description")}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <TableClearSection
                  userId={userId}
                  clientType={clientType !== "all" ? clientType : undefined}
                  isOwner={isOwner}
                  viewerUserId={currentUser?.id ?? null}
                  authInitialized={authInitialized}
                  targetUsername={profileUser.username}
                  clearVisibilitySource={clearVisibilitySource}
                  onClearVisibilitySourceChange={(next) =>
                    replaceParams({ cv: next === "viewer" ? "mine" : null })
                  }
                />
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
              enabled={showRatingOverview}
              isOwner={isOwner}
            />
          </TabsContent>

          <TabsContent value="activity" className="space-y-4">
            {currentTab === "activity" && activityDate ? (
              <CalendarDayDetail
                userId={userId}
                date={activityDate}
                clientType={clientType}
                onBack={handleBackToActivity}
                backLabel={t("dashboard.dayDetail.backToActivity")}
                isOwner={isOwner}
                hasNote={noteDatesSet.has(activityDate)}
                username={profileUser.username}
                avatarUrl={profileUser.avatar_url}
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
                    <div className="min-w-0 space-y-1.5">
                      <CardTitle>{t("dashboard.activityOverview.heatmapTitle")}</CardTitle>
                      <CardDescription>{t("dashboard.activityOverview.heatmapDescription")}</CardDescription>
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
                            {t(cat.labelKey)}
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
                        <span className="sr-only">Loading...</span>
                      </div>
                    ) : (
                      <ActivityHeatmap
                        data={heatmapData?.data ?? []}
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
                    <div className="min-w-0 space-y-1.5">
                      <CardTitle>{t("dashboard.activityOverview.graphTitle")}</CardTitle>
                      <CardDescription>{t("dashboard.activityOverview.graphDescription")}</CardDescription>
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
                            {t(cat.labelKey)}
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
                      <div className="h-[280px] animate-pulse rounded bg-muted">
                        <span className="sr-only">Loading...</span>
                      </div>
                    ) : (
                      <ActivityBarChart
                        data={barData?.data ?? []}
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
                    <div className="min-w-0 space-y-1.5">
                      <CardTitle>{t("dashboard.activityOverview.ratingGraphTitle")}</CardTitle>
                      <CardDescription>{t("dashboard.activityOverview.ratingGraphDescription")}</CardDescription>
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
                            {value === "exp" ? "EXP" : value === "rating" ? "Rating" : "BMSFORCE"}
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
                        loading={isActivityRatingHistoryDataLoading}
                        active={showActivityOverview}
                      />
                    ) : (
                      <div className="flex h-[300px] items-center justify-center text-body text-muted-foreground">
                        {t("dashboard.activityOverview.selectTable")}
                      </div>
                    )}
                  </CardContent>
                </Card>

                <RecentActivity
                  clientType={clientType}
                  heatmapData={heatmapData?.data ?? []}
                  ratingUpdatesByDate={heatmapRatingMap}
                  firstSyncDates={firstSyncDates}
                  onDayClick={handleActivityDayClick}
                  emptyMessage={isOwner ? t("dashboard.activity.noRecords") : t("common.states.noRecords")}
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
                backLabel={t("dashboard.calendar.back")}
                isOwner={isOwner}
                hasNote={noteDatesSet.has(calendarDate)}
                username={profileUser.username}
                avatarUrl={profileUser.avatar_url}
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
                  <CardTitle>{t("dashboard.calendar.title")}</CardTitle>
                  <CardDescription>{t("dashboard.calendar.description")}</CardDescription>
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
                    ratingUpdatesData={calendarRatingUpdatesData}
                    ratingUpdatesPending={calendarRatingUpdatesPending}
                    noteDates={noteDatesSet}
                    renderNoteIndicator={(dateStr) => (
                      <DayNotePopover
                        userId={userId}
                        date={dateStr}
                        isOwner={isOwner}
                        triggerVariant="cell"
                      />
                    )}
                  />
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {isOwner && (
            <TabsContent value="goals">
              <GoalsPanel isOwner={isOwner} />
            </TabsContent>
          )}
        </Tabs>
      </main>
    </div>
  );
}
