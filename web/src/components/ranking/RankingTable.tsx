"use client";

import Image from "next/image";
import Link from "next/link";
import { TooltipProvider } from "@/components/ui/tooltip";
import { resolveAvatarUrl } from "@/lib/avatar";
import { cn } from "@/lib/utils";
import { DecoratedUsername } from "./DecoratedUsername";
import { MetricInfoIcon } from "./RatingMetricInfo";
import { BmsforceValue } from "./BmsforceValue";
import type { RankingEntry, RankingType } from "@/lib/ranking-types";

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
        이 난이도표에는 아직 기록된 랭킹이 없습니다.
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
          <span className="text-center">순위</span>
          <span>닉네임</span>
          {type === "exp" && (
            <span className="flex items-center justify-end text-right">
              레벨
              <MetricInfoIcon metric="level" />
            </span>
          )}
          {type === "bmsforce" && (
            <span className="flex items-center justify-end text-right">
              레이팅
              <MetricInfoIcon metric="rating" />
            </span>
          )}
          <span className="flex items-center justify-end text-right">
            {type === "exp" ? "경험치" : "BMSFORCE"}
            <MetricInfoIcon metric={type === "exp" ? "exp" : "bmsforce"} />
          </span>
        </div>

        {/* Rows */}
        {entries.map((entry) => {
          const isMe = myUserId === entry.user_id;
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
              {/* 순위 */}
              <div className="text-center tabular-nums font-semibold text-lg text-foreground">
                {entry.rank}
              </div>

              {/* 닉네임 + 아바타 */}
              <div className="flex items-center gap-3 min-w-0">
                {entry.avatar_url ? (
                  <Image
                    src={resolveAvatarUrl(entry.avatar_url)}
                    alt={entry.username}
                    width={44}
                    height={44}
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

              {/* 레벨 / 레이팅 */}
              {type === "exp" && (
                <div className="text-right tabular-nums font-medium text-muted-foreground text-base">
                  Lv.{entry.exp_level ?? 0}
                </div>
              )}
              {type === "bmsforce" && (
                <div className="text-right tabular-nums font-medium text-muted-foreground text-base">
                  {Math.round(entry.rating ?? 0).toLocaleString()}
                </div>
              )}

              {/* 경험치 / BMSFORCE */}
              <div className="text-right tabular-nums font-semibold text-lg">
                {type === "exp" &&
                  (entry.exp ?? 0).toLocaleString(undefined, {
                    maximumFractionDigits: 0,
                  })}
                {type === "bmsforce" && (
                  <BmsforceValue value={entry.bms_force ?? 0} />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </TooltipProvider>
  );
}
