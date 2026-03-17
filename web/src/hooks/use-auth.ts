"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth";

/**
 * Auth hook for protected pages.
 * Fetches the current user on mount and redirects to /login if unauthenticated.
 *
 * @param requireAuth - If true (default), redirect to /login when not authenticated.
 */
export function useAuth(requireAuth = true) {
  const { user, isLoading, isInitialized, fetchUser } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (!isInitialized) {
      fetchUser();
    }
  }, [isInitialized, fetchUser]);

  useEffect(() => {
    if (isInitialized && requireAuth && !user) {
      router.push("/login");
    }
  }, [isInitialized, requireAuth, user, router]);

  return { user, isLoading: !isInitialized || isLoading };
}
