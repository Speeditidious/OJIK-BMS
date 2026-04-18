"use client";

import { Suspense, use } from "react";
import { UserDashboardContent } from "@/components/dashboard/UserDashboardContent";

export default function UserDashboardPage({
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
      <UserDashboardContent userId={userId} />
    </Suspense>
  );
}
