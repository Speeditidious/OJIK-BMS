"use client";

import { Suspense, useCallback, useEffect, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CalendarDays, RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Navbar } from "@/components/layout/navbar";
import { useAuthStore } from "@/stores/auth";
import {
  useWeeklyCategories,
  useWeeklyDetail,
  useWeeklyPeriods,
  useWeeklyRolloverInfo,
} from "@/hooks/use-weeklies";
import { WeeklyCategorySelector } from "@/components/weekly/WeeklyCategorySelector";
import { WeeklyBracketSelector } from "@/components/weekly/WeeklyBracketSelector";
import { WeeklyPeriodNav } from "@/components/weekly/WeeklyPeriodNav";
import { WeeklyFumenList } from "@/components/weekly/WeeklyFumenList";
import { readLastWeekly, saveLastWeekly, resolvePosition } from "@/lib/weekly-storage";
import {
  getWeeklyPeriodForOffset,
  getWeeklyValidOffsetRange,
  getWeeklyWeekNumber,
} from "@/lib/weekly-period.mjs";
import { formatRollover } from "@/lib/weekly-format.mjs";

function WeeklyContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t, i18n } = useTranslation();
  const { user } = useAuthStore();

  const { data: categories } = useWeeklyCategories();
  const { data: rolloverInfo } = useWeeklyRolloverInfo();

  const category = searchParams.get("category");
  const bracket = searchParams.get("bracket");
  const offset = parseInt(searchParams.get("offset") ?? "0", 10) || 0;

  const updateParams = useCallback(
    (updates: Record<string, string>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [k, v] of Object.entries(updates)) params.set(k, v);
      router.replace(`/weekly?${params.toString()}`);
    },
    [router, searchParams],
  );

  useEffect(() => {
    if (!categories || categories.length === 0) return;
    const requested = category && bracket ? { category, bracket } : readLastWeekly(user?.id);
    const resolved = resolvePosition(categories, requested);
    if (resolved) {
      const changed = resolved.category !== category || resolved.bracket !== bracket;
      if (changed) {
        updateParams({ category: resolved.category, bracket: resolved.bracket, offset: "0" });
      }
    }
  }, [categories, category, bracket, updateParams, user?.id]);

  useEffect(() => {
    if (category && bracket) saveLastWeekly(user?.id, { category, bracket });
  }, [category, bracket, user?.id]);

  const currentCategory = categories?.find((c) => c.key === category) ?? null;
  const { data: periods } = useWeeklyPeriods(category, bracket);
  const { data: detail, isLoading } = useWeeklyDetail(category, bracket, offset);
  const fallbackPeriod = useMemo(
    () => (rolloverInfo ? getWeeklyPeriodForOffset(new Date(), offset, rolloverInfo) : null),
    [offset, rolloverInfo],
  );
  const currentFallbackPeriod = useMemo(
    () => (rolloverInfo ? getWeeklyPeriodForOffset(new Date(), 0, rolloverInfo) : null),
    [rolloverInfo],
  );
  const displayPeriod = useMemo(
    () =>
      detail
        ? {
            periodStart: detail.period_start,
            periodEnd: detail.period_end,
            isCurrent: detail.is_current,
          }
        : fallbackPeriod,
    [detail, fallbackPeriod],
  );

  const validOffsetRange = useMemo(
    () =>
      periods && currentFallbackPeriod
        ? getWeeklyValidOffsetRange(periods, currentFallbackPeriod.periodStart)
        : null,
    [periods, currentFallbackPeriod],
  );
  const weekNumber = useMemo(
    () => (periods && displayPeriod ? getWeeklyWeekNumber(periods, displayPeriod.periodStart) : null),
    [periods, displayPeriod],
  );
  const isAtFirstPeriod = validOffsetRange ? offset <= validOffsetRange.minOffset : false;

  const handleCategorySelect = useCallback(
    (c: string) => {
      const firstBracket = categories?.find((x) => x.key === c)?.brackets[0]?.key ?? "";
      updateParams({ category: c, bracket: firstBracket });
    },
    [categories, updateParams],
  );

  useEffect(() => {
    if (!validOffsetRange) return;
    if (offset < validOffsetRange.minOffset) {
      updateParams({ offset: String(validOffsetRange.minOffset) });
      return;
    }
    if (offset > validOffsetRange.maxOffset) {
      updateParams({ offset: String(validOffsetRange.maxOffset) });
    }
  }, [offset, updateParams, validOffsetRange]);

  return (
    <div className="container max-w-4xl py-6 space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <CalendarDays className="h-7 w-7 text-primary" />
          <h1 className="text-3xl font-bold">{t("weekly.title")}</h1>
        </div>
        {rolloverInfo && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground bg-secondary/50 rounded-md px-3 py-1.5">
            <RefreshCw className="h-3 w-3 shrink-0" />
            <span>{formatRollover(rolloverInfo, i18n.language)}</span>
          </div>
        )}
      </div>

      {categories && (
        <div className="flex flex-col items-center gap-4">
          <WeeklyCategorySelector
            categories={categories}
            selected={category ?? ""}
            onSelect={handleCategorySelect}
          />
          {currentCategory && (
            <WeeklyBracketSelector
              brackets={currentCategory.brackets}
              selected={bracket ?? ""}
              onSelect={(b) => updateParams({ bracket: b })}
            />
          )}
        </div>
      )}

      {displayPeriod && (
        <WeeklyPeriodNav
          periodStart={displayPeriod.periodStart}
          periodEnd={displayPeriod.periodEnd}
          isCurrent={displayPeriod.isCurrent}
          weekNumber={weekNumber}
          isAtFirstPeriod={isAtFirstPeriod}
          offset={offset}
          onOffsetChange={(o) => updateParams({ offset: String(o) })}
          onCurrentPeriodClick={() => updateParams({ offset: "0" })}
        />
      )}

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-16 rounded-lg bg-secondary animate-pulse" />
          ))}
        </div>
      ) : detail ? (
        detail.fumens.length > 0 ? (
          <WeeklyFumenList weeklyId={detail.weekly_id} fumens={detail.fumens} myUserId={user?.id ?? null} />
        ) : (
          <p className="text-center text-muted-foreground py-8">{t("weekly.empty")}</p>
        )
      ) : (
        <p className="text-center text-muted-foreground py-8">{t("weekly.notFound")}</p>
      )}
    </div>
  );
}

export default function WeeklyPage() {
  return (
    <>
      <Navbar />
      <main>
        <Suspense>
          <WeeklyContent />
        </Suspense>
      </main>
    </>
  );
}
