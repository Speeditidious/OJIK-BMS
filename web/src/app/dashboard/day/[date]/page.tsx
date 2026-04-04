"use client";

import { use } from "react";
import { useRouter } from "next/navigation";
import { ChevronLeft, CalendarDays } from "lucide-react";
import { Navbar } from "@/components/layout/navbar";
import { UpdateRow } from "@/components/dashboard/RecentActivity";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useRecentUpdates, ClientTypeFilter } from "@/hooks/use-analysis";
import { useAuth } from "@/hooks/use-auth";

interface PageProps {
  params: Promise<{ date: string }>;
  searchParams: Promise<{ client_type?: string }>;
}

export default function DayDetailPage({ params, searchParams }: PageProps) {
  const { date } = use(params);
  const { client_type: rawClient } = use(searchParams);
  const clientType: ClientTypeFilter =
    rawClient === "lr2" || rawClient === "beatoraja" ? rawClient : "all";

  const { isLoading: authLoading } = useAuth(true);
  const { data, isLoading } = useRecentUpdates(200, clientType, date);
  const router = useRouter();

  const [y, m, d] = date.split("-").map(Number);

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container mx-auto px-4 py-8 max-w-2xl">
        <Button
          variant="ghost"
          size="sm"
          className="mb-4 -ml-1 gap-1.5 text-muted-foreground hover:text-foreground"
          onClick={() => router.back()}
        >
          <ChevronLeft className="h-4 w-4" />
          캘린더로 돌아가기
        </Button>

        <div className="flex items-center gap-2 mb-6">
          <CalendarDays className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-bold">
            {y}년 {m}월 {d}일의 기록
          </h1>
        </div>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              기록 갱신
              {data && (
                <span className="text-body font-normal text-muted-foreground">
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
              <p className="text-body text-muted-foreground py-4 text-center">
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
      </main>
    </div>
  );
}
