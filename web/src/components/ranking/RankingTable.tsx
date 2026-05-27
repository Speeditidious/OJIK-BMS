"use client";

import Link from "next/link";
import { useTranslation } from "react-i18next";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AvatarImage } from "@/components/common/AvatarImage";
import { resolveAvatarUrl } from "@/lib/avatar";
import { cn } from "@/lib/utils";
import { DecoratedUsername } from "./DecoratedUsername";
import { MetricInfoIcon } from "./RatingMetricInfo";
import { BmsforceValue } from "./BmsforceValue";
import type { RankingEntry, RankingType } from "@/lib/ranking-types";

const MASKED_RANKING_VALUE = "-";

interface RankingTableProps {
  entries: RankingEntry[];
  type: RankingType;
  myUserId?: string | null;
  isLoading: boolean;
}

export function RankingTable({
  entries,
  type,
  myUserId,
  isLoading,
}: RankingTableProps) {
  const { t } = useTranslation();

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 10 }).map((_, i) => (
          <div
            key={i}
            className="h-12 rounded-md bg-secondary animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (!entries.length) {
    return (
      <div className="py-16 text-center text-muted-foreground">
        {t("ranking.empty")}
      </div>
    );
  }

  const gridCols =
    type === "exp"
      ? "grid-cols-[3.5rem_minmax(0,1fr)_6rem_9rem]"
      : "grid-cols-[3.5rem_minmax(0,1fr)_7rem_9rem]";

  return (
    <TooltipProvider delayDuration={150}>
      <div className="rounded-lg border border-border overflow-hidden">
        {/* Header */}
        <div
          className={cn(
            "grid gap-4 px-5 py-3 bg-secondary/50 border-b border-border",
            "text-body font-semibold text-muted-foreground",
            gridCols,
          )}
        >
          <span className="text-center">{t("ranking.rank")}</span>
          <span>{t("ranking.nickname")}</span>
          {type === "exp" && (
            <span className="flex items-center justify-end text-right">
              {t("ranking.level")}
              <MetricInfoIcon metric="level" />
            </span>
          )}
          {type === "bmsforce" && (
            <span className="flex items-center justify-end text-right">
              {t("ranking.rating")}
              <MetricInfoIcon metric="rating" />
            </span>
          )}
          <span className="flex items-center justify-end text-right">
            {type === "exp" ? t("ranking.exp") : "BMSFORCE"}
            <MetricInfoIcon metric={type === "exp" ? "exp" : "bmsforce"} />
          </span>
        </div>

        {/* Rows */}
        {entries.map((entry) => {
          const isMe = myUserId === entry.user_id;
          const hasRankingValue = (entry.exp ?? 0) > 0;
          return (
            <div
              key={entry.user_id}
              className={cn(
                "grid gap-3 px-5 py-3.5 items-center text-base sm:gap-4",
                "border-b border-border last:border-b-0 transition-colors",
                gridCols,
                isMe ? "bg-primary/5 dark:bg-primary/10" : "hover:bg-secondary/30",
              )}
            >
              {/* Rank */}
              <div className="text-center tabular-nums font-semibold text-lg text-foreground">
                {hasRankingValue
                  ? entry.rank.toLocaleString()
                  : MASKED_RANKING_VALUE}
              </div>

              {/* Nickname + avatar */}
              <div className="flex items-center gap-3 min-w-0">
                {entry.avatar_url ? (
                  <AvatarImage
                    src={resolveAvatarUrl(entry.avatar_url)}
                    alt={entry.username}
                    size={44}
                    fallbackText={entry.username}
                    className="rounded-full object-cover flex-shrink-0"
                  />
                ) : (
                  <div className="w-11 h-11 rounded-full bg-primary/20 flex items-center justify-center text-body font-medium text-primary flex-shrink-0">
                    {entry.username.charAt(0).toUpperCase()}
                  </div>
                )}
                <Link
                  href={`/users/${entry.user_id}/dashboard`}
                  className="min-w-0 cursor-pointer"
                >
                  <DecoratedUsername
                    username={entry.username}
                    danDecoration={entry.dan_decoration}
                    className="text-lg sm:text-xl font-semibold leading-none tracking-[0.02em] truncate block"
                  />
                </Link>
              </div>

              {/* Level / Rating */}
              {type === "exp" && (
                <div className="text-right tabular-nums font-medium text-muted-foreground text-base">
                  {hasRankingValue
                    ? `Lv.${entry.exp_level ?? 0}`
                    : MASKED_RANKING_VALUE}
                </div>
              )}
              {type === "bmsforce" && (
                <div className="text-right tabular-nums font-medium text-muted-foreground text-base">
                  {hasRankingValue
                    ? Math.round(entry.rating ?? 0).toLocaleString()
                    : MASKED_RANKING_VALUE}
                </div>
              )}

              {/* EXP / BMSFORCE */}
              <div className="text-right tabular-nums font-semibold text-lg">
                {type === "exp" &&
                  (hasRankingValue
                    ? (entry.exp ?? 0).toLocaleString(undefined, {
                        maximumFractionDigits: 0,
                      })
                    : MASKED_RANKING_VALUE)}
                {type === "bmsforce" && (
                  hasRankingValue
                    ? <BmsforceValue value={entry.bms_force ?? 0} />
                    : MASKED_RANKING_VALUE
                )}
              </div>
            </div>
          );
        })}
      </div>
    </TooltipProvider>
  );
}
