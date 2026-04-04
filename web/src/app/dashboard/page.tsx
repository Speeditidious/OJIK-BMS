"use client";

import { useState, useMemo, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { LayoutDashboard, CalendarDays, ChevronLeft, TrendingUp, Music2, Clock, Hammer, HelpCircle } from "lucide-react";
import { Navbar } from "@/components/layout/navbar";
import { StatsGrid } from "@/components/dashboard/StatsGrid";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { ScoreUpdates } from "@/components/dashboard/ScoreUpdates";
import { TableClearSection } from "@/components/dashboard/TableClearSection";
import { ActivityHeatmap } from "@/components/charts/ActivityHeatmap";
import { ActivityBarChart } from "@/components/charts/ActivityBarChart";
import { ActivityCalendar } from "@/components/charts/ActivityCalendar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
  useActivityHeatmap,
  useActivityBar,
  usePlaySummary,
  useRecentUpdates,
  useCourseActivity,

  ClientTypeFilter,
} from "@/hooks/use-analysis";
import { useAuth } from "@/hooks/use-auth";

function formatPlaytime(seconds: number): string {
  if (seconds <= 0) return "0분";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}시간 ${m}분`;
  return `${m}분`;
}

function DayStatCard({
  title,
  value,
  sub,
  icon: Icon,
  uncertain,
  uncertainTooltip,
}: {
  title: string;
  value: string;
  sub: string;
  icon: React.ElementType;
  uncertain?: boolean;
  uncertainTooltip?: string;
}) {
  return (
    <Card className="border-dashed">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1 pt-3 px-4">
        <p className="text-label font-medium">{title}</p>
        <Icon className="h-3.5 w-3.5 text-muted-foreground" />
      </CardHeader>
      <CardContent className="pb-3 px-4">
        <div className="text-stat font-bold">
          {uncertain && uncertainTooltip ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="inline-flex items-center gap-1 text-muted-foreground cursor-help">
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

function CalendarDayDetail({
  date,
  clientType,
  onBack,
}: {
  date: string;
  clientType: ClientTypeFilter;
  onBack: () => void;
}) {
  const { data } = useRecentUpdates(1, clientType, date);
  const [y, m, d] = date.split("-").map(Number);

  return (
    <div className="space-y-4">
      <Button
        variant="ghost"
        size="sm"
        className="-ml-1 gap-1.5 text-muted-foreground hover:text-foreground"
        onClick={onBack}
      >
        <ChevronLeft className="h-4 w-4" />
        캘린더로 돌아가기
      </Button>
      <div className="flex items-center gap-2">
        <CalendarDays className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-bold">{y}년 {m}월 {d}일의 기록</h2>
      </div>

      {/* Day summary cards */}
      {data?.day_summary && (
        <TooltipProvider>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <DayStatCard
              title="갱신 수"
              value={`${data.day_summary.total_updates}`}
              sub="당일 기록 갱신"
              icon={TrendingUp}
            />
            <DayStatCard
              title="플레이 수"
              value={`${data.day_summary.total_play_count ?? 0}`}
              sub="당일 플레이 횟수"
              icon={Music2}
              uncertain={data.day_summary.play_count_uncertain}
              uncertainTooltip="첫 동기화 당일 혹은 그 이전 기록의 플레이 횟수는 집계할 수 없습니다."
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

      <ScoreUpdates clientType={clientType} date={date} />
    </div>
  );
}

const CURRENT_YEAR = new Date().getFullYear();
const CURRENT_MONTH = new Date().getMonth() + 1;
const BAR_RANGE_OPTIONS = [7, 30, 90] as const;

// ── Inner content (uses useSearchParams) ─────────────────────────────────────

function DashboardContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const { user, isLoading } = useAuth(true);
  const [clientType, setClientType] = useState<ClientTypeFilter>("all");
  const [heatmapYear, setHeatmapYear] = useState(CURRENT_YEAR);
  const [barDays, setBarDays] = useState<(typeof BAR_RANGE_OPTIONS)[number]>(30);
  const [activityView, setActivityView] = useState<"updates" | "plays">("updates");

  // Calendar tab state (local — preserved across URL-only navigation)
  const [calYear, setCalYear] = useState(CURRENT_YEAR);
  const [calMonth, setCalMonth] = useState(CURRENT_MONTH);

  // URL-derived navigation state
  const currentTab = searchParams.get("tab") ?? "distribution";
  const selectedDate = searchParams.get("date");

  const { data: heatmapData, isLoading: heatmapLoading } = useActivityHeatmap(heatmapYear, clientType);
  const { data: barData, isLoading: barLoading } = useActivityBar(barDays, clientType);
  const { data: summaryData } = usePlaySummary("all");

  // Calendar tab: load heatmap for the calendar year
  const { data: calHeatmapData } = useActivityHeatmap(calYear, clientType);
  // Per-client heatmaps for the "all" tab — used to show LR2/Beatoraja split in the calendar
  const { data: calLr2Data } = useActivityHeatmap(calYear, "lr2");
  const { data: calBeatorajaData } = useActivityHeatmap(calYear, "beatoraja");

  // Course activity data for overlays
  const { data: heatmapCourseData } = useCourseActivity(heatmapYear, undefined, clientType);
  const { data: barCourseData } = useCourseActivity(undefined, barDays, clientType);
  const { data: calCourseData } = useCourseActivity(calYear, undefined, clientType);

  const firstSyncDates = useMemo(() => {
    const map = summaryData?.first_synced_by_client;
    if (!map) return undefined;
    return {
      lr2: map.lr2 ? map.lr2.slice(0, 10) : undefined,
      beatoraja: map.beatoraja ? map.beatoraja.slice(0, 10) : undefined,
    };
  }, [summaryData]);

  function handleTabChange(value: string) {
    router.push(`/dashboard?tab=${value}`, { scroll: false });
  }

  function handleDayClick(dateStr: string) {
    router.push(`/dashboard?tab=calendar&date=${dateStr}`, { scroll: false });
  }

  function handleBackToCalendar() {
    router.push(`/dashboard?tab=calendar`, { scroll: false });
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container mx-auto px-4 py-8">
        <div className="flex items-center gap-3 mb-6">
          <LayoutDashboard className="h-8 w-8 text-primary" />
          <div>
            <h1 className="text-3xl font-bold">대시보드</h1>
            {user && (
              <p className="text-muted-foreground text-body mt-0.5">
                환영합니다,{" "}
                <span className="text-foreground font-medium">{user.username}</span>님
              </p>
            )}
          </div>
        </div>

        <StatsGrid clientType={clientType} onClientTypeChange={setClientType} />

        <Tabs
          value={currentTab}
          onValueChange={handleTabChange}
          className="space-y-4"
        >
          <TabsList>
            <TabsTrigger value="distribution">클리어 분포</TabsTrigger>
            <TabsTrigger value="activity">활동 요약</TabsTrigger>
            <TabsTrigger value="calendar">활동 캘린더</TabsTrigger>
          </TabsList>

          {/* Tab 1: Clear distribution by difficulty table */}
          <TabsContent value="distribution">
            <Card>
              <CardHeader>
                <CardTitle>난이도표 클리어 분포</CardTitle>
                <CardDescription>
                  난이도표 레벨별 클리어 현황. 막대를 클릭하면 해당 레벨/클리어 타입으로 필터링됩니다.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <TableClearSection clientType={clientType !== "all" ? clientType : undefined} />
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tab 2: Activity heatmap + trend chart + recent activity feed */}
          <TabsContent value="activity" className="space-y-4">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>활동 히트맵</CardTitle>
                    <CardDescription>연도별로 얼마나 열심히 했는지 한 눈에 확인하세요</CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex gap-0.5">
                      {(["updates", "plays"] as const).map((v) => (
                        <Button
                          key={v}
                          variant={activityView === v ? "secondary" : "ghost"}
                          size="sm"
                          className="text-label h-7 px-2"
                          onClick={() => setActivityView(v)}
                        >
                          {v === "updates" ? "기록 갱신" : "플레이 횟수"}
                        </Button>
                      ))}
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setHeatmapYear((y) => y - 1)}
                      >
                        ‹
                      </Button>
                      <span className="text-body font-medium w-12 text-center">{heatmapYear}</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setHeatmapYear((y) => Math.min(y + 1, CURRENT_YEAR))}
                        disabled={heatmapYear >= CURRENT_YEAR}
                      >
                        ›
                      </Button>
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {heatmapLoading ? (
                  <div className="h-24 bg-muted rounded animate-pulse" />
                ) : (
                  <ActivityHeatmap data={heatmapData?.data ?? []} year={heatmapYear} firstSyncDates={firstSyncDates} clientType={clientType} courseData={heatmapCourseData ?? []} viewMode={activityView} />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>활동 그래프</CardTitle>
                    <CardDescription>기록 갱신 또는 플레이 횟수 추이를 그래프로 확인하세요</CardDescription>
                  </div>
                  <div className="flex gap-1">
                    {BAR_RANGE_OPTIONS.map((d) => (
                      <Button
                        key={d}
                        variant={barDays === d ? "secondary" : "ghost"}
                        size="sm"
                        className="text-label h-7 px-2"
                        onClick={() => setBarDays(d)}
                      >
                        {d}일
                      </Button>
                    ))}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {barLoading ? (
                  <div className="h-48 bg-muted rounded animate-pulse" />
                ) : (
                  <ActivityBarChart data={barData?.data ?? []} firstSyncDates={firstSyncDates} clientType={clientType} courseData={barCourseData ?? []} viewMode={activityView} />
                )}
              </CardContent>
            </Card>

            <RecentActivity clientType={clientType} />
          </TabsContent>

          {/* Tab 3: Monthly calendar */}
          <TabsContent value="calendar" className="space-y-4">
            {selectedDate ? (
              <CalendarDayDetail
                date={selectedDate}
                clientType={clientType}
                onBack={handleBackToCalendar}
              />
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle>활동 캘린더</CardTitle>
                  <CardDescription>날짜를 클릭하면 해당 날의 기록을 확인합니다.</CardDescription>
                </CardHeader>
                <CardContent>
                  <ActivityCalendar
                    data={calHeatmapData?.data ?? []}
                    year={calYear}
                    month={calMonth}
                    onDayClick={handleDayClick}
                    onMonthChange={(y, m) => {
                      setCalYear(y);
                      setCalMonth(m);
                    }}
                    firstSyncDates={firstSyncDates}
                    dataLr2={clientType === "all" ? calLr2Data?.data : undefined}
                    dataBeatoraja={clientType === "all" ? calBeatorajaData?.data : undefined}
                    courseData={calCourseData ?? []}
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

// ── Export with Suspense (required for useSearchParams in Next.js) ─────────────

export default function DashboardPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
      </div>
    }>
      <DashboardContent />
    </Suspense>
  );
}
