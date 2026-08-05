"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useRecentActivity } from "@/hooks/use-user-activity";
import { AvatarImage } from "@/components/common/AvatarImage";
import { NumberedPagination } from "@/components/common/NumberedPagination";
import { resolveAvatarUrl } from "@/lib/avatar";
import { timeAgo } from "@/lib/time";

const PAGE_SIZE = 13;

/**
 * Recent-activity tab content: a public feed of recent syncs (last 30 days)
 * that actually changed something, offset-paginated with numbered page
 * buttons — matches the ranking page's `Pagination` control rather than an
 * infinite "load more" feed.
 */
export function RecentActivityFeed() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);

  const { data, isLoading } = useRecentActivity(PAGE_SIZE, page);
  const items = data?.items ?? [];
  const totalPages = data ? Math.max(1, Math.ceil(data.total_count / PAGE_SIZE)) : 1;

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 min-h-4 flex items-center justify-between gap-3 text-caption text-muted-foreground">
        <span>{t("home.activity.recent.window")}</span>
        {data?.computed_at && (
          <span className="ml-auto text-right">
            {t("home.activity.lastComputedAt", { time: timeAgo(data.computed_at, t) })}
          </span>
        )}
      </div>

      <div className="flex-1 rounded-lg border border-border overflow-hidden">
        <div className="flex items-center gap-3 px-3 py-2 border-b border-border bg-secondary/50 text-caption font-semibold text-muted-foreground">
          <span className="min-w-0 flex-1">{t("home.activity.recent.columns.user")}</span>
          <span className="flex-shrink-0">{t("home.activity.recent.columns.clientTime")}</span>
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
            {t("home.activity.recent.empty")}
          </div>
        ) : (
          items.map((item) => (
            <div
              key={item.id}
              className="flex items-center gap-3 px-3 py-2 border-b border-border/50 last:border-0"
            >
              <div className="min-w-0 flex-1">
                <div className="group inline-flex max-w-full items-center gap-3 align-middle">
                  <a
                    href={`/users/${item.user_id}/dashboard?tab=calendar&calendar_date=${item.sync_date}`}
                    className="flex-shrink-0"
                  >
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
                    href={`/users/${item.user_id}/dashboard?tab=calendar&calendar_date=${item.sync_date}`}
                    className="min-w-0 truncate text-label font-semibold text-foreground transition-colors group-hover:text-primary hover:text-primary"
                  >
                    {item.username}
                  </a>
                </div>
              </div>
              <span className="flex items-center gap-1 flex-shrink-0">
                {item.updated_client_types.map((clientType) => (
                  <span
                    key={clientType}
                    className="rounded-full bg-secondary px-2 py-0.5 text-caption text-muted-foreground"
                  >
                    {t(`home.activity.recent.client.${clientType.toLowerCase()}`, {
                      defaultValue: clientType.toUpperCase(),
                    })}
                  </span>
                ))}
              </span>
              <span className="flex-shrink-0 text-caption text-muted-foreground">·</span>
              <span className="flex-shrink-0 text-caption text-muted-foreground">
                {timeAgo(item.synced_at, t)}
              </span>
            </div>
          ))
        )}
      </div>

      <NumberedPagination page={page} totalPages={totalPages} onChange={setPage} />
    </div>
  );
}
