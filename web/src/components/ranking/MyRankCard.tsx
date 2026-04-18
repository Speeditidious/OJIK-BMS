"use client";

import Image from "next/image";
import Link from "next/link";
import { TooltipProvider } from "@/components/ui/tooltip";
import { resolveAvatarUrl } from "@/lib/avatar";
import { timeAgo } from "@/lib/time";
import type { AuthUser } from "@/stores/auth";
import type { MyRankData, RankingType } from "@/lib/ranking-types";
import { DecoratedUsername } from "./DecoratedUsername";
import { MetricInfoIcon } from "./RatingMetricInfo";

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
  if (!isLoggedIn || !user) return null;

  const metaInfo =
    data && data.status === "ok" ? (
      <div className="flex flex-col gap-0.5 text-label text-muted-foreground text-right">
        {data.last_synced_at && (
          <span>플레이 데이터 동기화: {timeAgo(data.last_synced_at)}</span>
        )}
        {data.calculated_at && (
          <span>레이팅 계산 적용: {timeAgo(data.calculated_at)}</span>
        )}
        {data.last_synced_at &&
          data.calculated_at &&
          new Date(data.last_synced_at) > new Date(data.calculated_at) && (
            <span className="text-yellow-500/80">동기화 후 아직 랭킹에 미반영</span>
          )}
      </div>
    ) : null;

  let body: React.ReactNode;

  if (!tableSlug || isLoading) {
    body = <div className="animate-pulse h-14 rounded-md bg-secondary/60" />;
  } else if (!data || data.status === "no_scores") {
    body = (
      <p className="text-body text-muted-foreground">
        아직 기록이 없습니다. 클라이언트를 통해 플레이 데이터를 동기화해보세요.
      </p>
    );
  } else if (data.status === "pending") {
    body = (
      <p className="text-body text-muted-foreground">
        플레이 데이터는 감지되었지만 랭킹 계산이 아직 반영되지 않았습니다. 잠시 후 새로고침해주세요.
      </p>
    );
  } else {
    body = (
      <div className="flex flex-col items-center justify-center gap-4 text-center">
        {/* Rank info */}
        <div className="flex flex-wrap items-start justify-center gap-6">
          {type === "exp" ? (
            <>
              <div>
                <p className="text-body-sm text-muted-foreground">내 순위</p>
                <p className="text-2xl font-bold">
                  #{(data.exp_rank ?? 0).toLocaleString()}
                  <span className="text-body-sm text-muted-foreground font-normal">
                    {" "}/ {data.exp_total_users.toLocaleString()}
                  </span>
                </p>
              </div>
              <div>
                <p className="flex items-center justify-center text-body-sm text-muted-foreground">
                  레벨
                  <MetricInfoIcon metric="level" />
                </p>
                <div className="flex flex-wrap items-center justify-center gap-2">
                  <p className="text-2xl font-bold">Lv.{data.exp_level}</p>
                  {data.is_max_level && (
                    <span className="inline-flex items-center rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-caption font-medium text-primary">
                      MAX
                    </span>
                  )}
                </div>
              </div>
              <div>
                <p className="flex items-center justify-center text-body-sm text-muted-foreground">
                  경험치
                  <MetricInfoIcon metric="exp" />
                </p>
                <p className="text-2xl font-bold tabular-nums">
                  {data.exp.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </p>
              </div>
            </>
          ) : (
            /* bmsforce */
            <>
              <div>
                <p className="text-body-sm text-muted-foreground">내 순위</p>
                <p className="text-2xl font-bold">
                  #{(data.bms_force_rank ?? 0).toLocaleString()}
                  <span className="text-body-sm text-muted-foreground font-normal">
                    {" "}/ {data.bms_force_total_users.toLocaleString()}
                  </span>
                </p>
              </div>
              <div>
                <p className="flex items-center justify-center text-body-sm text-muted-foreground">
                  TOP {data.top_n} 레이팅 합산
                  <MetricInfoIcon metric="rating" />
                </p>
                <p className="text-2xl font-bold tabular-nums">
                  {data.rating.toFixed(2)}
                </p>
              </div>
              <div>
                <p className="flex items-center justify-center text-body-sm text-muted-foreground">
                  BMSFORCE
                  <MetricInfoIcon metric="bmsforce" />
                </p>
                <p className="text-2xl font-bold tabular-nums">
                  {data.bms_force.toFixed(3)}
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

        {/* Header: 아이덴티티 */}
        <div className="min-w-0 flex justify-center">
          <Link
            href={`/users/${user.id}/dashboard`}
            className="group flex flex-col items-center gap-3.5 min-w-0 w-fit max-w-full text-center"
          >
            {user.avatar_url ? (
              <Image
                src={resolveAvatarUrl(user.avatar_url)}
                alt={user.username}
                width={48}
                height={48}
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

        {/* Body: 순위/수치 블록 */}
        {body}
      </section>
    </TooltipProvider>
  );
}
