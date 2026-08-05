"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useActivityRanking } from "@/hooks/use-user-activity";
import { useAuthStore } from "@/stores/auth";
import { AvatarImage } from "@/components/common/AvatarImage";
import { resolveAvatarUrl } from "@/lib/avatar";
import { rankClass } from "@/lib/rank-color";
import { cn } from "@/lib/utils";
import type { ActivityMetric, ActivityRankingItem } from "@/types";

const METRICS: ActivityMetric[] = ["attendance", "plays", "notes_hit"];

/** Maps the API's snake_case metric value to the camelCase i18n key segment. */
const I18N_METRIC_KEY: Record<ActivityMetric, string> = {
  attendance: "attendance",
  plays: "plays",
  notes_hit: "notesHit",
};

/** Sentinel for "no page has been merged into `items` yet". */
const NOT_MERGED = Symbol("not-merged");

/**
 * Activity ranking tab content: sub-tabs for 3 metrics (attendance / plays /
 * notes_hit), each backed by a paginated 30-day leaderboard snapshot.
 *
 * Pagination follows the same pattern as `RecentActivityFeed`: items are
 * merged into local state by adjusting state directly during render (React's
 * documented pattern for "derived state from a changing key" — see
 * https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes),
 * guarded by `mergedKey` tracking which `metric:rankAfter` page was last
 * merged — not appended inside the "load more" click handler off a stale
 * closed-over `data`. `useActivityRanking` uses `placeholderData:
 * keepPreviousData` so the list doesn't blank to a loading skeleton while
 * the next page (or a new metric) is in flight.
 */
export function ActivityRankingPanel() {
  const { t } = useTranslation();
  const { user } = useAuthStore();
  const [metric, setMetric] = useState<ActivityMetric>("attendance");
  const [rankAfter, setRankAfter] = useState(0);
  const [items, setItems] = useState<ActivityRankingItem[]>([]);
  const [hasNextPage, setHasNextPage] = useState(false);
  const [nextRankAfter, setNextRankAfter] = useState<number | null>(null);
  const [mergedKey, setMergedKey] = useState<string | typeof NOT_MERGED>(NOT_MERGED);

  const { data, isFetching } = useActivityRanking(metric, 10, rankAfter);
  const i18nMetric = I18N_METRIC_KEY[metric];
  const pageKey = `${metric}:${rankAfter}`;

  if (data && !isFetching && mergedKey !== pageKey) {
    setMergedKey(pageKey);
    setItems((prev) => (rankAfter === 0 ? data.items : [...prev, ...data.items]));
    setHasNextPage(data.has_next_page);
    setNextRankAfter(data.next_rank_after);
  }

  const isInitialLoading = items.length === 0 && isFetching;

  const handleMetricChange = (value: ActivityMetric) => {
    setMetric(value);
    setRankAfter(0);
    setItems([]);
    setHasNextPage(false);
    setNextRankAfter(null);
  };

  const handleLoadMore = () => {
    if (nextRankAfter !== null) setRankAfter(nextRankAfter);
  };

  const myRow = data?.my_rank ?? null;
  const myRowInPage = user ? items.some((item) => item.user_id === user.id) : false;
  const showMyRankSummary = Boolean(user && myRow && !myRowInPage);

  return (
    <div>
      <Tabs value={metric} onValueChange={(value) => handleMetricChange(value as ActivityMetric)}>
        <TabsList className="grid w-full grid-cols-3">
          {METRICS.map((m) => (
            <TabsTrigger key={m} value={m}>
              {t(`home.activity.metric.${I18N_METRIC_KEY[m]}.label`)}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <p className="mt-2 text-caption text-muted-foreground">
        {t(`home.activity.metric.${i18nMetric}.desc`)}
      </p>

      {metric === "plays" && (
        <p className="mt-1 rounded-md bg-secondary/50 px-3 py-2 text-caption text-muted-foreground">
          {t("home.activity.metric.plays.notice")}
        </p>
      )}

      {data && data.computed_at === null ? (
        <div className="py-10 text-center text-label text-muted-foreground">
          {t("home.activity.ranking.pending")}
        </div>
      ) : (
        <>
          {data?.window_start && data?.window_end && (
            <p className="mt-3 text-caption text-muted-foreground">
              {t("home.activity.ranking.window", { start: data.window_start, end: data.window_end })}
              {data.computed_at && (
                <>
                  {" · "}
                  {t("home.activity.ranking.updatedAt", { time: new Date(data.computed_at).toLocaleString() })}
                </>
              )}
            </p>
          )}

          <div className="mt-2 rounded-lg border border-border overflow-hidden">
            {isInitialLoading ? (
              Array.from({ length: 10 }).map((_, index) => (
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
                  <a
                    key={item.user_id}
                    href={`/users/${item.user_id}/dashboard`}
                    className={cn(
                      "flex items-center gap-3 px-3 py-2 border-b border-border/50 last:border-0 transition-colors",
                      isMe ? "bg-primary/5 dark:bg-primary/10 border-primary/30" : "hover:bg-secondary/40",
                    )}
                  >
                    <span className={cn("w-8 flex-shrink-0 text-center tabular-nums font-bold", rankClass(item.rank))}>
                      {item.rank}
                    </span>
                    {item.avatar_url ? (
                      <AvatarImage
                        src={resolveAvatarUrl(item.avatar_url)}
                        alt={item.username}
                        size={32}
                        fallbackText={item.username}
                        className="rounded-full object-cover flex-shrink-0"
                      />
                    ) : (
                      <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-label font-medium text-primary flex-shrink-0">
                        {item.username.charAt(0).toUpperCase()}
                      </div>
                    )}
                    <span className="min-w-0 flex-1 truncate text-label text-foreground">
                      {item.username}
                    </span>
                    <span className="flex-shrink-0 tabular-nums text-label font-semibold text-foreground">
                      {t(`home.activity.metric.${i18nMetric}.unit`, { count: item.value })}
                    </span>
                  </a>
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

          {hasNextPage && (
            <div className="mt-3 flex justify-center">
              <button
                type="button"
                onClick={handleLoadMore}
                disabled={isFetching}
                className={cn(
                  "rounded-md border border-border px-4 py-1.5 text-label text-muted-foreground transition-colors hover:bg-secondary/40 hover:text-foreground",
                  isFetching && "opacity-60",
                )}
              >
                {t("home.activity.ranking.loadMore")}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
