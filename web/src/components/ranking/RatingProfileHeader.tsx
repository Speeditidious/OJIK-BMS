"use client";

import Image from "next/image";
import { TooltipProvider } from "@/components/ui/tooltip";
import { resolveAvatarUrl } from "@/lib/avatar";
import { timeAgo } from "@/lib/time";
import type { MyRankData } from "@/lib/ranking-types";
import type { UserPublicRead } from "@/hooks/use-user-profile";
import { DecoratedUsername } from "./DecoratedUsername";
import { RatingExpProgressBar } from "./RatingExpProgressBar";
import { MetricInfoIcon } from "./RatingMetricInfo";
import { BmsforceValue } from "./BmsforceValue";

interface RatingProfileHeaderProps {
  profileUser: UserPublicRead;
  data: MyRankData | null | undefined;
  isLoading: boolean;
}

export function RatingProfileHeader({
  profileUser,
  data,
  isLoading,
}: RatingProfileHeaderProps) {
  if (isLoading) {
    return <div className="h-44 rounded-xl border border-border bg-card/60 animate-pulse" />;
  }

  const avatar = profileUser.avatar_url ? (
    <Image
      src={resolveAvatarUrl(profileUser.avatar_url)}
      alt={profileUser.username}
      width={72}
      height={72}
      className="rounded-full object-cover"
    />
  ) : (
    <div className="w-[72px] h-[72px] rounded-full bg-primary/15 text-primary flex items-center justify-center text-2xl font-bold">
      {profileUser.username.charAt(0).toUpperCase()}
    </div>
  );

  const metaInfo = data && data.status === "ok" ? (
    <div className="flex flex-col gap-0.5 text-label text-muted-foreground">
      {data.last_synced_at && <span>플레이 데이터 동기화: {timeAgo(data.last_synced_at)}</span>}
      {data.calculated_at && <span>레이팅 계산 적용: {timeAgo(data.calculated_at)}</span>}
      {data.last_synced_at && data.calculated_at && new Date(data.last_synced_at) > new Date(data.calculated_at) && (
        <span className="text-warning">동기화 후 아직 랭킹에 미반영</span>
      )}
    </div>
  ) : null;

  let body: React.ReactNode;
  if (!data || data.status === "no_scores") {
    body = (
      <p className="text-body text-muted-foreground">
        아직 동기화된 플레이 기록이 없습니다. 클라이언트에서 데이터를 동기화하면 레이팅 상세가 표시됩니다.
      </p>
    );
  } else if (data.status === "pending") {
    body = (
      <p className="text-body text-muted-foreground">
        플레이 데이터는 감지되었지만 랭킹 계산이 아직 반영되지 않았습니다. 잠시 후 다시 확인해주세요.
      </p>
    );
  } else {
    body = (
      <div className="space-y-4">
        <div className="grid gap-3 md:grid-cols-4">
          <div className="rounded-lg border border-border/60 bg-secondary/30 px-4 py-3">
            <p className="flex items-center text-label text-muted-foreground">
              현재 경험치
              <MetricInfoIcon metric="exp" />
            </p>
            <p className="text-stat font-bold">{Math.round(data.exp).toLocaleString()}</p>
          </div>
          <div className="rounded-lg border border-border/60 bg-secondary/30 px-4 py-3">
            <p className="flex items-center text-label text-muted-foreground">
              현재 레벨
              <MetricInfoIcon metric="level" />
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-stat font-bold">Lv.{data.exp_level}</p>
              {data.is_max_level && (
                <span className="inline-flex items-center rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-caption font-medium text-primary">
                  MAX
                </span>
              )}
            </div>
          </div>
          <div className="rounded-lg border border-border/60 bg-secondary/30 px-4 py-3">
            <p className="flex items-center text-label text-muted-foreground">
              TOP {data.top_n} 레이팅 합산
              <MetricInfoIcon metric="rating" />
            </p>
            <p className="text-stat font-bold">{Math.round(data.rating).toLocaleString()}</p>
          </div>
          <div className="rounded-lg border border-border/60 bg-secondary/30 px-4 py-3">
            <p className="flex items-center text-label text-muted-foreground">
              BMSFORCE
              <MetricInfoIcon metric="bmsforce" />
            </p>
            <p className="text-stat font-bold">
              <BmsforceValue value={data.bms_force} />
            </p>
          </div>
        </div>
        <RatingExpProgressBar
          progressRatio={data.exp_level_progress_ratio}
          expToNextLevel={data.exp_to_next_level}
          isMaxLevel={data.is_max_level}
          maxLevel={data.max_level}
        />
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={150}>
      <section className="rounded-xl border border-primary/20 bg-card/80 px-5 py-5 space-y-4">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="flex items-center gap-4 min-w-0">
            {avatar}
            <div className="inline-flex min-w-0 flex-col items-start">
              <DecoratedUsername
                username={profileUser.username}
                danDecoration={data?.dan_decoration ?? null}
                className="text-2xl font-bold truncate block"
              />
            </div>
          </div>
          {metaInfo}
        </div>
        {body}
      </section>
    </TooltipProvider>
  );
}
