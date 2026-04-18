"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowRight, UserCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { resolveAvatarUrl } from "@/lib/avatar";
import { formatJoinDate, timeAgo } from "@/lib/time";

interface DashboardUserHeaderProps {
  username: string;
  avatarUrl: string | null;
  userId: string;
  createdAt: string;
  lastSyncedAt: string | null;
}

export function DashboardUserHeader({
  username,
  avatarUrl,
  userId,
  createdAt,
  lastSyncedAt,
}: DashboardUserHeaderProps) {
  return (
    <section className="flex flex-col gap-4 rounded-xl border border-border bg-card/70 p-5 sm:flex-row sm:items-start">
      {avatarUrl ? (
        <Image
          src={resolveAvatarUrl(avatarUrl)}
          alt=""
          width={64}
          height={64}
          className="rounded-full object-cover ring-2 ring-primary/30"
        />
      ) : (
        <div
          aria-hidden="true"
          className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/20 text-2xl font-bold text-primary ring-2 ring-primary/30"
        >
          {username.charAt(0).toUpperCase()}
        </div>
      )}

      <div className="min-w-0 flex-1 space-y-1">
        <h1 className="text-2xl font-bold">{username}</h1>
        <p className="text-body text-muted-foreground">가입일: {formatJoinDate(createdAt)}</p>
        <p className="text-body text-muted-foreground">
          플레이 데이터 동기화: {lastSyncedAt ? timeAgo(lastSyncedAt) : "아직 동기화 기록 없음"}
        </p>
      </div>

      <Button asChild size="lg" className="w-full gap-2 shadow-sm sm:w-auto sm:shrink-0">
        <Link href={`/users/${userId}`}>
          <UserCircle className="h-5 w-5" />
          <span className="font-semibold">프로필 보기</span>
          <ArrowRight className="h-4 w-4" />
        </Link>
      </Button>
    </section>
  );
}
