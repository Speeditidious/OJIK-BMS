"use client";

import { Suspense, use, useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { UserCircle } from "lucide-react";
import { Navbar } from "@/components/layout/navbar";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { ProfileActionBar } from "@/components/profile/ProfileActionBar";
import { ProfileInfoCard } from "@/components/profile/ProfileInfoCard";
import { AboutMeCard } from "@/components/profile/AboutMeCard";
import { useActivityHeatmap, usePlaySummary } from "@/hooks/use-analysis";
import { useUserProfile } from "@/hooks/use-user-profile";
import { useAuthStore } from "@/stores/auth";
import { getInitialBrowserPathname, restoreInitialBrowserUrlIfNeeded } from "@/lib/static-route";

const CURRENT_YEAR = new Date().getFullYear();

function UserProfileContent({ userId }: { userId: string }) {
  const { t } = useTranslation();
  const currentUser = useAuthStore((state) => state.user);
  const isOwner = currentUser?.id === userId;

  const { data: profileUser, isLoading, error } = useUserProfile(userId);
  const { data: heatmapData } = useActivityHeatmap(CURRENT_YEAR, "all", userId);
  const { data: summaryData } = usePlaySummary("all", userId);

  const heatmapRatingMap = useMemo(
    () => Object.fromEntries((heatmapData?.data ?? []).map((day) => [day.date, day.rating_updates ?? 0])),
    [heatmapData?.data],
  );
  const firstSyncDates = useMemo(() => {
    const map = summaryData?.first_synced_by_client;
    if (!map) return undefined;
    return {
      lr2: map.lr2 ? map.lr2.slice(0, 10) : undefined,
      beatoraja: map.beatoraja ? map.beatoraja.slice(0, 10) : undefined,
    };
  }, [summaryData]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error || !profileUser) {
    return (
      <div className="min-h-screen bg-background">
        <Navbar />
        <main className="container mx-auto px-4 py-8">
          <p className="text-muted-foreground">{t("common.states.notFound")}</p>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container mx-auto space-y-6 px-4 py-8">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <UserCircle className="h-7 w-7 text-primary" />
            <h1 className="text-3xl font-bold">{t("common.nav.profile")}</h1>
          </div>
          <ProfileActionBar isOwner={isOwner} />
        </div>

        <div>
          <ProfileInfoCard
            username={profileUser.username}
            avatarUrl={profileUser.avatar_url}
            createdAt={profileUser.created_at}
            lastSyncedAt={profileUser.last_synced_at}
            dashboardHref={`/users/${userId}/dashboard`}
          />
        </div>

        <AboutMeCard bio={profileUser.bio} isOwner={isOwner} />

        <RecentActivity
          heatmapData={heatmapData?.data ?? []}
          ratingUpdatesByDate={heatmapRatingMap}
          firstSyncDates={firstSyncDates}
          onDayClick={(date) => window.location.assign(`/users/${userId}/dashboard?tab=calendar&calendar_date=${date}`)}
          emptyMessage={isOwner ? t("dashboard.activity.noRecords") : t("common.states.noRecords")}
        />
      </main>
    </div>
  );
}

export default function UserProfilePage({
  params,
}: {
  params: Promise<{ userId: string }>;
}) {
  const { userId: routeUserId } = use(params);
  const pathname = getInitialBrowserPathname();
  const pathnameUserId = pathname.match(/^\/users\/([^/?#]+)\/?$/)?.[1];
  const userId = pathnameUserId ?? routeUserId;

  useEffect(() => {
    restoreInitialBrowserUrlIfNeeded();
  }, []);

  return (
    <Suspense
      fallback={(
        <div className="flex min-h-screen items-center justify-center bg-background">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      )}
    >
      <UserProfileContent userId={userId} />
    </Suspense>
  );
}
