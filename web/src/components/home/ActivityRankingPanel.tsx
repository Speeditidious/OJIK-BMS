"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useActivityRanking } from "@/hooks/use-user-activity";
import { useAuthStore } from "@/stores/auth";
import { AvatarImage } from "@/components/common/AvatarImage";
import { NumberedPagination } from "@/components/common/NumberedPagination";
import { resolveAvatarUrl } from "@/lib/avatar";
import { rankClass } from "@/lib/rank-color";
import { timeAgo } from "@/lib/time";
import { cn } from "@/lib/utils";
import type { ActivityMetric, ActivityRange } from "@/types";

const PAGE_SIZE = 11;
const RANGES: ActivityRange[] = ["weekly", "monthly"];
const METRICS: ActivityMetric[] = ["attendance", "plays", "notes_hit"];

/** Maps the API's snake_case metric value to the camelCase i18n key segment. */
const I18N_METRIC_KEY: Record<ActivityMetric, string> = {
  attendance: "attendance",
  plays: "plays",
  notes_hit: "notesHit",
};

/**
 * Activity ranking tab content: sub-tabs for 3 metrics (attendance / plays /
 * notes_hit), each backed by an offset-paginated 30-day leaderboard snapshot.
 *
 * Uses numbered page buttons (the shared `Pagination` control) rather than an
 * infinite "load more" feed, matching the ranking page.
 */
export function ActivityRankingPanel() {
  const { t } = useTranslation();
  const { user } = useAuthStore();
  const [range, setRange] = useState<ActivityRange>("monthly");
  const [metric, setMetric] = useState<ActivityMetric>("attendance");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useActivityRanking(range, metric, PAGE_SIZE, page);
  const displayedData = data?.range === range && data.metric === metric ? data : undefined;
  const i18nMetric = I18N_METRIC_KEY[metric];
  const items = displayedData?.items ?? [];
  const totalPages = displayedData ? Math.max(1, Math.ceil(displayedData.total_count / PAGE_SIZE)) : 1;

  const handleMetricChange = (value: ActivityMetric) => {
    setMetric(value);
    setPage(1);
  };

  const handleRangeChange = (value: ActivityRange) => {
    setRange(value);
    setPage(1);
  };

  const myRow = displayedData?.my_rank ?? null;
  const myRowInPage = user ? items.some((item) => item.user_id === user.id) : false;
  const showMyRankSummary = Boolean(user && myRow && !myRowInPage);

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 min-h-4 flex items-center justify-between gap-3 text-caption text-muted-foreground">
        <span />
        {displayedData?.computed_at && (
          <span className="ml-auto text-right">
            {t("home.activity.lastComputedAt", { time: timeAgo(displayedData.computed_at, t) })}
          </span>
        )}
      </div>

      <Tabs value={range} onValueChange={(value) => handleRangeChange(value as ActivityRange)}>
        <TabsList className="grid w-full grid-cols-2">
          {RANGES.map((r) => (
            <TabsTrigger key={r} value={r}>
              {t(`home.activity.ranking.range.${r}`)}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <div className="mt-3 flex justify-center">
        <Tabs value={metric} onValueChange={(value) => handleMetricChange(value as ActivityMetric)}>
          <TabsList className="grid grid-cols-3 w-80">
            {METRICS.map((m) => {
              const metricKey = I18N_METRIC_KEY[m];
              return (
                <TabsTrigger
                  key={m}
                  value={m}
                  title={t(`home.activity.metric.${metricKey}.desc`)}
                >
                  {t(`home.activity.metric.${metricKey}.label`)}
                </TabsTrigger>
              );
            })}
          </TabsList>
        </Tabs>
      </div>

      {displayedData && displayedData.computed_at === null ? (
        <div className="py-10 text-center text-label text-muted-foreground">
          {t("home.activity.ranking.pending")}
        </div>
      ) : (
        <>
          <div className="mt-3 flex-1 rounded-lg border border-border overflow-hidden">
            <div className="flex items-center gap-3 px-3 py-2 border-b border-border bg-secondary/50 text-caption font-semibold text-muted-foreground">
              <span className="w-8 flex-shrink-0 text-center">{t("home.activity.ranking.columns.rank")}</span>
              <span className="min-w-0 flex-1">{t("home.activity.ranking.columns.user")}</span>
              <span className="flex-shrink-0">{t(`home.activity.metric.${i18nMetric}.label`)}</span>
            </div>

            {isLoading ? (
              Array.from({ length: PAGE_SIZE }).map((_, index) => (
                <div
                  key={index}
                  className="h-11 border-b border-border/50 last:border-0 bg-secondary/30 animate-pulse"
                />
              ))
            ) : items.length === 0 ? (
              <div className="py-10 text-center text-label text-muted-foreground">
                {t("home.activity.ranking.empty")}
              </div>
            ) : (
              items.map((item) => {
                const isMe = user?.id === item.user_id;
                return (
                  <div
                    key={item.user_id}
                    className={cn(
                      "flex items-center gap-3 px-3 py-2 border-b border-border/50 last:border-0",
                      isMe && "bg-primary/5 dark:bg-primary/10 border-primary/30",
                    )}
                  >
                    <span className={cn("w-8 flex-shrink-0 text-center tabular-nums font-bold", rankClass(item.rank))}>
                      {item.rank}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="group inline-flex max-w-full items-center gap-3 align-middle">
                        <a href={`/users/${item.user_id}/dashboard`} className="flex-shrink-0">
                          {item.avatar_url ? (
                            <AvatarImage
                              src={resolveAvatarUrl(item.avatar_url)}
                              alt={item.username}
                              size={32}
                              fallbackText={item.username}
                              className="rounded-full object-cover"
                            />
                          ) : (
                            <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-label font-medium text-primary">
                              {item.username.charAt(0).toUpperCase()}
                            </div>
                          )}
                        </a>
                        <a
                          href={`/users/${item.user_id}/dashboard`}
                          className="min-w-0 truncate text-label font-semibold text-foreground transition-colors group-hover:text-primary hover:text-primary"
                        >
                          {item.username}
                        </a>
                      </div>
                    </div>
                    <span className="flex-shrink-0 tabular-nums text-label font-semibold text-foreground">
                      {t(`home.activity.metric.${i18nMetric}.unit`, { count: item.value })}
                    </span>
                  </div>
                );
              })
            )}

            {showMyRankSummary && myRow && (
              <div className="flex items-center gap-3 px-3 py-2 bg-primary/10 border-t border-primary/30">
                <span className="w-8 flex-shrink-0 text-center text-caption text-muted-foreground">
                  {t("home.activity.ranking.myRank")}
                </span>
                <span className={cn("flex-shrink-0 tabular-nums font-bold", rankClass(myRow.rank))}>
                  {myRow.rank}
                </span>
                <span className="min-w-0 flex-1" />
                <span className="flex-shrink-0 tabular-nums text-label font-semibold text-foreground">
                  {t(`home.activity.metric.${i18nMetric}.unit`, { count: myRow.value })}
                </span>
              </div>
            )}
          </div>

          <NumberedPagination page={page} totalPages={totalPages} onChange={setPage} />
        </>
      )}
    </div>
  );
}
