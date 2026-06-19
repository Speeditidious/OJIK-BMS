"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import { setTokens } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

export default function CallbackPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const { fetchUser } = useAuthStore();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const accessToken = params.get("access_token");
    const refreshToken = params.get("refresh_token");
    const error = params.get("error");

    if (error) {
      const messages: Record<string, string> = {
        account_banned: t("auth.callback.errors.accountBanned"),
        oauth_token_failed: t("auth.callback.errors.oauthTokenFailed"),
        oauth_user_failed: t("auth.callback.errors.oauthUserFailed"),
      };
      const msg = messages[error] ?? t("auth.callback.errors.default");
      router.push(`/login?error=${encodeURIComponent(msg)}`);
      return;
    }

    if (accessToken && refreshToken) {
      setTokens(accessToken, refreshToken);
      fetchUser().then(() => {
        const currentUser = useAuthStore.getState().user;
        if (currentUser) {
          window.location.assign(`/users/${currentUser.id}/dashboard`);
        } else {
          router.push("/login");
        }
      });
    } else {
      router.push("/login");
    }
  }, [router, fetchUser, t]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center">
        <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-4" />
        <p className="text-muted-foreground">{t("auth.callback.processing")}</p>
      </div>
    </div>
  );
}
