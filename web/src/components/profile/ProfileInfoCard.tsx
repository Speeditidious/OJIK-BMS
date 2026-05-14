"use client";

import Image from "next/image";
import Link from "next/link";
import { useTranslation } from "react-i18next";
import { ArrowRight, LayoutDashboard } from "lucide-react";
import { Button } from "@/components/ui/button";
import { resolveAvatarUrl } from "@/lib/avatar";
import { formatJoinDate, timeAgo } from "@/lib/time";

interface ProfileInfoCardProps {
  username: string;
  avatarUrl: string | null;
  createdAt: string;
  lastSyncedAt: string | null;
  dashboardHref: string;
}

export function ProfileInfoCard({
  username,
  avatarUrl,
  createdAt,
  lastSyncedAt,
  dashboardHref,
}: ProfileInfoCardProps) {
  const { t } = useTranslation();

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
        <p className="text-body text-muted-foreground">{t("profile.info.joinedAt", { date: formatJoinDate(createdAt, t) })}</p>
        <p className="text-body text-muted-foreground">
          {lastSyncedAt ? t("profile.info.syncedAt", { time: timeAgo(lastSyncedAt, t) }) : t("profile.info.neverSynced")}
        </p>
      </div>

      <Button asChild size="lg" className="w-full gap-2 shadow-sm sm:w-auto sm:shrink-0">
        <Link href={dashboardHref}>
          <LayoutDashboard className="h-5 w-5" />
          <span className="font-semibold">{t("profile.info.viewDashboard")}</span>
          <ArrowRight className="h-4 w-4" />
        </Link>
      </Button>
    </section>
  );
}
