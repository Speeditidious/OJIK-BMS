"use client";

import { use, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth";

export default function DashboardDayRedirectPage({
  params,
  searchParams,
}: {
  params: Promise<{ date: string }>;
  searchParams: Promise<{ client_type?: string }>;
}) {
  const { date } = use(params);
  const { client_type } = use(searchParams);
  const router = useRouter();
  const { user, isInitialized, fetchUser } = useAuthStore();

  useEffect(() => {
    if (!isInitialized) {
      fetchUser();
      return;
    }
    if (user) {
      const query = client_type ? `&client_type=${client_type}` : "";
      router.replace(`/users/${user.id}/dashboard?tab=calendar&date=${date}${query}`);
    } else {
      router.replace("/login");
    }
  }, [user, isInitialized, fetchUser, router, date, client_type]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
    </div>
  );
}
