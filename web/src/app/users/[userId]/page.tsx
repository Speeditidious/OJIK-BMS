"use client";

import { Suspense, use } from "react";
import { useRouter } from "next/navigation";
import { UserCircle } from "lucide-react";
import { Navbar } from "@/components/layout/navbar";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { ProfileActionBar } from "@/components/profile/ProfileActionBar";
import { ProfileInfoCard } from "@/components/profile/ProfileInfoCard";
import { AboutMeCard } from "@/components/profile/AboutMeCard";
import { useActivityHeatmap } from "@/hooks/use-analysis";
import { useUserProfile } from "@/hooks/use-user-profile";
import { useAuthStore } from "@/stores/auth";

const CURRENT_YEAR = new Date().getFullYear();

function UserProfileContent({ userId }: { userId: string }) {
  const router = useRouter();
  const currentUser = useAuthStore((state) => state.user);
  const isOwner = currentUser?.id === userId;

  const { data: profileUser, isLoading, error } = useUserProfile(userId);
  const { data: heatmapData } = useActivityHeatmap(CURRENT_YEAR, "all", userId);

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
          <p className="text-muted-foreground">해당 유저를 찾을 수 없습니다.</p>
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
            <h1 className="text-3xl font-bold">프로필</h1>
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
          onDayClick={(date) => router.push(`/users/${userId}/dashboard?tab=calendar&date=${date}`)}
          emptyMessage={isOwner ? "동기화된 활동 내역이 없습니다." : "이 유저는 아직 공개된 활동 내역이 없습니다."}
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
  const { userId } = use(params);

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
