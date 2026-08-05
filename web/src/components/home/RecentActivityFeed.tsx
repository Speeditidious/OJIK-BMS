"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useRecentActivity } from "@/hooks/use-user-activity";
import { AvatarImage } from "@/components/common/AvatarImage";
import { resolveAvatarUrl } from "@/lib/avatar";
import { timeAgo } from "@/lib/time";
import { cn } from "@/lib/utils";
import type { RecentActivityItem } from "@/types";

/**
 * Recent-activity tab content: a public feed of recent syncs (last 30 days) that
 * actually changed something, paginated via a keyset cursor.
 *
 * Pagination is accumulated client-side: each "load more" click fetches the
 * next page with the latest cursor and appends its items to local state,
 * rather than replacing them. This keeps the component self-contained
 * without a generic infinite-query abstraction (none exists in this codebase yet).
 */
export function RecentActivityFeed() {
  const { t } = useTranslation();
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const [accumulated, setAccumulated] = useState<RecentActivityItem[]>([]);
  const { data, isLoading, isFetching } = useRecentActivity(10, cursor);

  const items = cursor === undefined ? (data?.items ?? []) : accumulated;
  const hasNextPage = data?.has_next_page ?? false;
  const isFirstPage = cursor === undefined;

  const handleLoadMore = () => {
    if (!data) return;
    setAccumulated((prev) => (isFirstPage ? data.items : [...prev, ...data.items]));
    if (data.next_cursor) setCursor(data.next_cursor);
  };

  return (
    <div>
      <p className="mb-2 text-caption text-muted-foreground">
        {t("home.activity.recent.window")}
      </p>

      <div className="rounded-lg border border-border overflow-hidden">
        {isLoading ? (
          Array.from({ length: 10 }).map((_, index) => (
            <div
              key={index}
              className="h-11 border-b border-border/50 last:border-0 bg-secondary/30 animate-pulse"
            />
          ))
        ) : items.length === 0 && isFirstPage ? (
          <div className="py-10 text-center text-label text-muted-foreground">
            {t("home.activity.recent.empty")}
          </div>
        ) : (
          items.map((item) => (
            <a
              key={item.id}
              href={`/users/${item.user_id}/dashboard?tab=calendar&calendar_date=${item.sync_date}`}
              className="flex items-center gap-3 px-3 py-2 border-b border-border/50 last:border-0 transition-colors hover:bg-secondary/40"
            >
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
              <span className="flex items-center gap-1 flex-shrink-0">
                {item.updated_client_types.map((clientType) => (
                  <span
                    key={clientType}
                    className="rounded-full bg-secondary px-2 py-0.5 text-caption text-muted-foreground"
                  >
                    {t(`home.activity.recent.client.${clientType.toLowerCase()}`)}
                  </span>
                ))}
              </span>
              <span className="flex-shrink-0 text-caption text-muted-foreground">·</span>
              <span className="flex-shrink-0 text-caption text-muted-foreground">
                {timeAgo(item.synced_at, t)}
              </span>
            </a>
          ))
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
            {t("home.activity.recent.loadMore")}
          </button>
        </div>
      )}
    </div>
  );
}
