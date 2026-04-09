"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth";

export default function DashboardRedirectPage() {
  const router = useRouter();
  const { user, isInitialized, fetchUser } = useAuthStore();

  useEffect(() => {
    if (!isInitialized) {
      fetchUser();
      return;
    }
    if (user) {
      router.replace(`/users/${user.id}`);
    } else {
      router.replace("/login");
    }
  }, [user, isInitialized, fetchUser, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
    </div>
  );
}
