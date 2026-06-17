"use client";

import { Suspense, use, useEffect } from "react";
import { UserDashboardContent } from "@/components/dashboard/UserDashboardContent";
import { getInitialBrowserPathname, restoreInitialBrowserUrlIfNeeded } from "@/lib/static-route";

export default function UserDashboardPage({
  params,
}: {
  params: Promise<{ userId: string }>;
}) {
  const { userId: routeUserId } = use(params);
  const pathname = getInitialBrowserPathname();
  const pathnameUserId = pathname.match(/^\/users\/([^/?#]+)\/dashboard\/?$/)?.[1];
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
      <UserDashboardContent userId={userId} />
    </Suspense>
  );
}
