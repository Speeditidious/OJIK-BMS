"use client";

import { useState, useMemo } from "react";
import { LayoutDashboard, CalendarDays, ChevronLeft } from "lucide-react";
import { Navbar } from "@/components/layout/navbar";
import { StatsGrid } from "@/components/dashboard/StatsGrid";
import { RecentActivity, UpdateRow, clearBadge } from "@/components/dashboard/RecentActivity";
import { TableClearSection } from "@/components/dashboard/TableClearSection";
import { DanBadgeShowcase } from "@/components/dashboard/DanBadgeShowcase";
import { ActivityHeatmap } from "@/components/charts/ActivityHeatmap";
import { ActivityBarChart } from "@/components/charts/ActivityBarChart";
import { ActivityCalendar } from "@/components/charts/ActivityCalendar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useActivityHeatmap,
  useActivityBar,
  usePlaySummary,
  useRecentUpdates,
  useCourseActivity,
  useNotesActivity,
  ClientTypeFilter,
  RecentUpdate,
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
  const { data, isLoading } = useRecentUpdates(20, clientType, date);
  const { data: courseData, isLoading: courseLoading } = useCourseActivity(
    undefined, undefined, clientType, date
  );
  const { data: notesData } = useNotesActivity(90, date);
  const [y, m, d] = date.split("-").map(Number);

  const { clearUpdates, scoreUpdates, otherUpdates } = useMemo(() => {
    const updates: RecentUpdate[] = data?.updates ?? [];
    const clearUpdates = updates.filter(
      (u) => u.clear_type !== u.old_clear_type && u.clear_type !== null && u.old_clear_type !== null
    );
    const clearSet = new Set(clearUpdates.map((u) => u.id));
    const scoreUpdates = updates.filter(
      (u) => !clearSet.has(u.id) && u.score !== u.old_score
    );
    const scoreSet = new Set(scoreUpdates.map((u) => u.id));
    const otherUpdates = updates.filter(
      (u) => !clearSet.has(u.id) && !scoreSet.has(u.id)
    );
    return { clearUpdates, scoreUpdates, otherUpdates };
  }, [data]);

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

      {/* Day summary bar */}
      {data?.day_summary && (
        <div className="flex justify-center gap-8 text-sm text-muted-foreground flex-wrap">
          <span>총 갱신 <strong className="text-foreground">{data.day_summary.total_updates}곡</strong></span>
          <span>총 플레이 <strong className="text-foreground">{data.day_summary.total_play_count}회</strong></span>
          {notesData && notesData.length > 0 && (
            <span>격파 노트 <strong className="text-foreground">{notesData[0].notes.toLocaleString()}</strong></span>
          )}
        </div>
      )}

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
            <div className="space-y-4">
              {clearUpdates.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Separator className="flex-1" />
                    <span className="text-[10px] text-muted-foreground shrink-0">클리어 갱신 {clearUpdates.length}건</span>
                    <Separator className="flex-1" />
                  </div>
                  {clearUpdates.map((u) => <UpdateRow key={u.id} u={u} />)}
                </div>
              )}
              {scoreUpdates.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Separator className="flex-1" />
                    <span className="text-[10px] text-muted-foreground shrink-0">스코어 갱신 {scoreUpdates.length}건</span>
                    <Separator className="flex-1" />
                  </div>
                  {scoreUpdates.map((u) => <UpdateRow key={u.id} u={u} />)}
                </div>
              )}
              {otherUpdates.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Separator className="flex-1" />
                    <span className="text-[10px] text-muted-foreground shrink-0">기타 갱신 {otherUpdates.length}건</span>
                    <Separator className="flex-1" />
                  </div>
                  {otherUpdates.map((u) => <UpdateRow key={u.id} u={u} />)}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Course records section */}
      {(courseLoading || (courseData && courseData.length > 0)) && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">
              코스 기록
              {courseData && (
                <span className="text-sm font-normal text-muted-foreground ml-2">
                  — {courseData.length}건
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {courseLoading ? (
              <div className="space-y-2">
                {[0, 1].map((i) => (
                  <div key={i} className="h-4 w-48 bg-muted rounded animate-pulse" />
                ))}
              </div>
            ) : (
              <div>
                {courseData!.map((c, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 py-2 border-b border-border/40 last:border-0"
                  >
                    {clearBadge(c.clear_type, c.client_type)}
                    <span className="text-xs font-mono text-muted-foreground">
                      {c.course_hash.slice(0, 8)}…
                    </span>
                    {c.song_count !== null && (
                      <span className="text-[10px] text-muted-foreground">({c.song_count}곡)</span>
                    )}
                    <span className="text-[10px] text-muted-foreground uppercase">{c.client_type}</span>
                    {c.is_first_clear && (
                      <span
                        className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium border shrink-0"
                        style={{ borderColor: "hsl(var(--warning)/0.6)", background: "hsl(var(--warning)/0.15)", color: "hsl(var(--warning))" }}
                      >
                        ★ 첫 클리어
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
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
            <TabsTrigger value="badges">단위 배지</TabsTrigger>
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
                  <ActivityHeatmap data={heatmapData?.data ?? []} year={heatmapYear} firstSyncDates={firstSyncDates} clientType={clientType} courseData={heatmapCourseData ?? []} />
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
                  <ActivityBarChart data={barData?.data ?? []} firstSyncDates={firstSyncDates} clientType={clientType} courseData={barCourseData ?? []} />
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
                    courseData={calCourseData ?? []}
                  />
                </CardContent>
              </Card>
            )}
          </TabsContent>
          {/* Tab 4: Dan badges showcase */}
          <TabsContent value="badges">
            <DanBadgeShowcase />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
