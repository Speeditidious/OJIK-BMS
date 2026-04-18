"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { setTokens } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

export default function CallbackPage() {
  const router = useRouter();
  const { fetchUser } = useAuthStore();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const accessToken = params.get("access_token");
    const refreshToken = params.get("refresh_token");
    const error = params.get("error");

    if (error) {
      const messages: Record<string, string> = {
        account_banned: "계정이 정지되었습니다.",
        oauth_token_failed: "Discord 인증에 실패했습니다.",
        oauth_user_failed: "Discord 사용자 정보를 가져오지 못했습니다.",
      };
      const msg = messages[error] ?? "로그인에 실패했습니다.";
      router.push(`/login?error=${encodeURIComponent(msg)}`);
      return;
    }

    if (accessToken && refreshToken) {
      setTokens(accessToken, refreshToken);
      fetchUser().then(() => {
        const currentUser = useAuthStore.getState().user;
        if (currentUser) {
          router.push(`/users/${currentUser.id}/dashboard`);
        } else {
          router.push("/login");
        }
      });
    } else {
      router.push("/login");
    }
  }, [router, fetchUser]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center">
        <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-4" />
        <p className="text-muted-foreground">로그인 처리 중...</p>
      </div>
    </div>
  );
}
