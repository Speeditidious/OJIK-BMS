"use client";

import { useState, useMemo } from "react";
import { LayoutDashboard, CalendarDays, ChevronLeft } from "lucide-react";
import { Navbar } from "@/components/layout/navbar";
import { StatsGrid } from "@/components/dashboard/StatsGrid";
import { RecentActivity, UpdateRow } from "@/components/dashboard/RecentActivity";
import { TableClearSection } from "@/components/dashboard/TableClearSection";
import { ActivityHeatmap } from "@/components/charts/ActivityHeatmap";
import { ActivityBarChart } from "@/components/charts/ActivityBarChart";
import { ActivityCalendar } from "@/components/charts/ActivityCalendar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useActivityHeatmap,
  useActivityBar,
  usePlaySummary,
  useRecentUpdates,
  ClientTypeFilter,
} from "@/hooks/use-analysis";
import { useAuth } from "@/hooks/use-auth";

function CalendarDayDetail({
  date,
  clientType,
  onBack,
}: {
  date: string;
  clientType: ClientTypeFilter;
  onBack: () => void;
}) {
  // limit is ignored by the API when date is provided (server uses effective_limit=200),
  // but must be ≤100 to pass API validation.
  const { data, isLoading } = useRecentUpdates(20, clientType, date);
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
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            기록 갱신
            {data && (
              <span className="text-sm font-normal text-muted-foreground">
                — {data.updates.length}건
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <div className="space-y-3">
              {[0, 1, 2].map((i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="h-4 w-32 bg-muted rounded animate-pulse" />
                  <div className="h-4 w-16 bg-muted rounded animate-pulse" />
                </div>
              ))}
            </div>
          )}
          {!isLoading && (!data || data.updates.length === 0) && (
            <p className="text-sm text-muted-foreground py-4 text-center">
              해당 날짜에 기록된 플레이 데이터가 없습니다.
            </p>
          )}
          {!isLoading && data && data.updates.length > 0 && (
            <div>
              {data.updates.map((u) => (
                <UpdateRow key={u.id} u={u} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

const CURRENT_YEAR = new Date().getFullYear();
const CURRENT_MONTH = new Date().getMonth() + 1;
const BAR_RANGE_OPTIONS = [7, 30, 90] as const;

export default function DashboardPage() {
  const { user, isLoading } = useAuth(true);
  const [clientType, setClientType] = useState<ClientTypeFilter>("all");
  const [heatmapYear, setHeatmapYear] = useState(CURRENT_YEAR);
  const [barDays, setBarDays] = useState<(typeof BAR_RANGE_OPTIONS)[number]>(30);

  // Calendar tab state
  const [calYear, setCalYear] = useState(CURRENT_YEAR);
  const [calMonth, setCalMonth] = useState(CURRENT_MONTH);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const { data: heatmapData, isLoading: heatmapLoading } = useActivityHeatmap(heatmapYear, clientType);
  const { data: barData, isLoading: barLoading } = useActivityBar(barDays, clientType);
  const { data: summaryData } = usePlaySummary("all");

  // Calendar tab: load heatmap for the calendar year
  const { data: calHeatmapData } = useActivityHeatmap(calYear, clientType);
  // Per-client heatmaps for the "all" tab — used to show LR2/Beatoraja split in the calendar
  const { data: calLr2Data } = useActivityHeatmap(calYear, "lr2");
  const { data: calBeatorajaData } = useActivityHeatmap(calYear, "beatoraja");

  const firstSyncDates = useMemo(() => {
    const map = summaryData?.first_synced_by_client;
    if (!map) return undefined;
    return {
      lr2: map.lr2 ? map.lr2.slice(0, 10) : undefined,
      beatoraja: map.beatoraja ? map.beatoraja.slice(0, 10) : undefined,
    };
  }, [summaryData]);

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
              <p className="text-muted-foreground text-sm mt-0.5">
                환영합니다,{" "}
                <span className="text-foreground font-medium">{user.username}</span>님
              </p>
            )}
          </div>
        </div>

        <StatsGrid clientType={clientType} onClientTypeChange={setClientType} />

        <Tabs
          defaultValue="distribution"
          className="space-y-4"
          onValueChange={(v) => { if (v !== "calendar") setSelectedDate(null); }}
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
                    <CardDescription>날짜별 스코어 갱신 횟수 (플레이 시간 기준)</CardDescription>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setHeatmapYear((y) => y - 1)}
                    >
                      ‹
                    </Button>
                    <span className="text-sm font-medium w-12 text-center">{heatmapYear}</span>
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
              </CardHeader>
              <CardContent>
                {heatmapLoading ? (
                  <div className="h-24 bg-muted rounded animate-pulse" />
                ) : (
                  <ActivityHeatmap data={heatmapData?.data ?? []} year={heatmapYear} firstSyncDates={firstSyncDates} clientType={clientType} />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>기록 갱신 추이</CardTitle>
                    <CardDescription>일별 스코어 갱신 횟수 (플레이 시간 기준)</CardDescription>
                  </div>
                  <div className="flex gap-1">
                    {BAR_RANGE_OPTIONS.map((d) => (
                      <Button
                        key={d}
                        variant={barDays === d ? "secondary" : "ghost"}
                        size="sm"
                        className="text-xs h-7 px-2"
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
                  <ActivityBarChart data={barData?.data ?? []} firstSyncDates={firstSyncDates} clientType={clientType} />
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
                onBack={() => setSelectedDate(null)}
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
                    onDayClick={setSelectedDate}
                    onMonthChange={(y, m) => {
                      setCalYear(y);
                      setCalMonth(m);
                    }}
                    firstSyncDates={firstSyncDates}
                    dataLr2={clientType === "all" ? calLr2Data?.data : undefined}
                    dataBeatoraja={clientType === "all" ? calBeatorajaData?.data : undefined}
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
