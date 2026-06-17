"use client";

import { use, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth";

export default function DashboardDayRedirectPage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date: routeDate } = use(params);
  const pathname = typeof window === "undefined" ? "" : window.location.pathname;
  const pathnameDate = pathname.match(/^\/dashboard\/day\/([^/?#]+)\/?$/)?.[1];
  const date = pathnameDate ?? routeDate;
  const router = useRouter();
  const { user, isInitialized, fetchUser } = useAuthStore();

  useEffect(() => {
    if (!isInitialized) {
      fetchUser();
      return;
    }
    if (user) {
      const client_type = new URLSearchParams(window.location.search).get("client_type");
      const query = client_type ? `&client_type=${client_type}` : "";
      router.replace(`/users/${user.id}/dashboard?tab=calendar&date=${date}${query}`);
    } else {
      router.replace("/login");
    }
  }, [user, isInitialized, fetchUser, router, date]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
    </div>
  );
}
