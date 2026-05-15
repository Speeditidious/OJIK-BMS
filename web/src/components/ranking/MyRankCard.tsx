"use client";

import Link from "next/link";
import { useTranslation } from "react-i18next";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AvatarImage } from "@/components/common/AvatarImage";
import { resolveAvatarUrl } from "@/lib/avatar";
import { timeAgo } from "@/lib/time";
import type { AuthUser } from "@/stores/auth";
import type { MyRankData, RankingType } from "@/lib/ranking-types";
import { DecoratedUsername } from "./DecoratedUsername";
import { MetricInfoIcon } from "./RatingMetricInfo";
import { BmsforceValue } from "./BmsforceValue";

const MASKED_RANKING_VALUE = "-";

interface MyRankCardProps {
  data: MyRankData | null | undefined;
  type: RankingType;
  isLoading: boolean;
  isLoggedIn: boolean;
  tableSlug: string | null;
  user: AuthUser | null;
}

export function MyRankCard({
  data,
  type,
  isLoading,
  isLoggedIn,
  tableSlug,
  user,
}: MyRankCardProps) {
  const { t } = useTranslation();

  if (!isLoggedIn || !user) return null;

  const metaInfo =
    data && data.status === "ok" ? (
      <div className="flex flex-col gap-0.5 text-label text-muted-foreground text-right">
        {data.last_synced_at && (
          <span>{t("ranking.profileHeader.syncedAt", { time: timeAgo(data.last_synced_at, t) })}</span>
        )}
        {data.calculated_at && (
          <span>{t("ranking.profileHeader.calculatedAt", { time: timeAgo(data.calculated_at, t) })}</span>
        )}
        {data.last_synced_at &&
          data.calculated_at &&
          new Date(data.last_synced_at) > new Date(data.calculated_at) && (
            <span className="text-yellow-500/80">{t("ranking.profileHeader.pending")}</span>
          )}
      </div>
    ) : null;

  let body: React.ReactNode;

  if (!tableSlug || isLoading) {
    body = <div className="animate-pulse h-14 rounded-md bg-secondary/60" />;
  } else if (!data || data.status === "no_scores") {
    body = (
      <p className="text-body text-muted-foreground">
        {t("ranking.profileHeader.noSyncedRecords")}
      </p>
    );
  } else if (data.status === "pending") {
    body = (
      <p className="text-body text-muted-foreground">
        {t("ranking.profileHeader.calculationPending")}
      </p>
    );
  } else {
    const hasRankingValue = data.exp > 0;
    body = (
      <div className="flex flex-col items-center justify-center gap-4 text-center">
        {/* Rank info */}
        <div className="flex flex-wrap items-start justify-center gap-6">
          {type === "exp" ? (
            <>
              <div>
                <p className="text-body-sm text-muted-foreground">{t("ranking.rank")}</p>
                <p className="text-2xl font-bold">
                  {hasRankingValue ? (
                    <>
                      #{(data.exp_rank ?? 0).toLocaleString()}
                      <span className="text-body-sm text-muted-foreground font-normal">
                        {" "}/ {data.exp_total_users.toLocaleString()}
                      </span>
                    </>
                  ) : (
                    MASKED_RANKING_VALUE
                  )}
                </p>
              </div>
              <div>
                <p className="flex items-center justify-center text-body-sm text-muted-foreground">
                  {t("ranking.level")}
                  <MetricInfoIcon metric="level" />
                </p>
                <div className="flex flex-wrap items-center justify-center gap-2">
                  <p className="text-2xl font-bold">
                    {hasRankingValue
                      ? `Lv.${data.exp_level}`
                      : MASKED_RANKING_VALUE}
                  </p>
                  {hasRankingValue && data.is_max_level && (
                    <span className="inline-flex items-center rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-caption font-medium text-primary">
                      MAX
                    </span>
                  )}
                </div>
              </div>
              <div>
                <p className="flex items-center justify-center text-body-sm text-muted-foreground">
                  {t("ranking.exp")}
                  <MetricInfoIcon metric="exp" />
                </p>
                <p className="text-2xl font-bold tabular-nums">
                  {hasRankingValue
                    ? data.exp.toLocaleString(undefined, { maximumFractionDigits: 0 })
                    : MASKED_RANKING_VALUE}
                </p>
              </div>
            </>
          ) : (
            /* bmsforce */
            <>
              <div>
                <p className="text-body-sm text-muted-foreground">{t("ranking.rank")}</p>
                <p className="text-2xl font-bold">
                  {hasRankingValue ? (
                    <>
                      #{(data.bms_force_rank ?? 0).toLocaleString()}
                      <span className="text-body-sm text-muted-foreground font-normal">
                        {" "}/ {data.bms_force_total_users.toLocaleString()}
                      </span>
                    </>
                  ) : (
                    MASKED_RANKING_VALUE
                  )}
                </p>
              </div>
              <div>
                <p className="flex items-center justify-center text-body-sm text-muted-foreground">
                  {t("ranking.profileHeader.topRatingSum", { n: data.top_n })}
                  <MetricInfoIcon metric="rating" />
                </p>
                <p className="text-2xl font-bold tabular-nums">
                  {hasRankingValue
                    ? Math.round(data.rating).toLocaleString()
                    : MASKED_RANKING_VALUE}
                </p>
              </div>
              <div>
                <p className="flex items-center justify-center text-body-sm text-muted-foreground">
                  BMSFORCE
                  <MetricInfoIcon metric="bmsforce" />
                </p>
                <p className="text-2xl font-bold tabular-nums">
                  {hasRankingValue
                    ? <BmsforceValue value={data.bms_force} />
                    : MASKED_RANKING_VALUE}
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={150}>
      <section className="rounded-lg border border-primary/30 bg-primary/5 p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <p className="text-lg font-bold tracking-normal text-foreground">
            MY RANKING
          </p>
          {metaInfo}
        </div>

        {/* Header: user identity */}
        <div className="min-w-0 flex justify-center">
          <Link
            href={`/users/${user.id}/dashboard`}
            className="group flex flex-col items-center gap-3.5 min-w-0 w-fit max-w-full text-center"
          >
            {user.avatar_url ? (
              <AvatarImage
                src={resolveAvatarUrl(user.avatar_url)}
                alt={user.username}
                size={48}
                className="rounded-full object-cover flex-shrink-0"
              />
            ) : (
              <div className="w-12 h-12 rounded-full bg-primary/20 flex items-center justify-center text-body font-medium text-primary flex-shrink-0">
                {user.username.charAt(0).toUpperCase()}
              </div>
            )}
            <div className="min-w-0">
              <DecoratedUsername
                username={user.username}
                danDecoration={data?.dan_decoration ?? null}
                className="font-bold text-xl sm:text-2xl leading-none tracking-[0.03em] truncate block transition-opacity group-hover:opacity-90"
              />
            </div>
          </Link>
        </div>

        {/* Body: rank/score block */}
        {body}
      </section>
    </TooltipProvider>
  );
}
