"use client";

import { useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Check } from "lucide-react";
import { useTranslation } from "react-i18next";

function DeleteCallbackContent() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const error = searchParams.get("error");

  useEffect(() => {
    if (token && window.opener) {
      window.opener.postMessage(
        { type: "ojik_delete_verified", token },
        window.location.origin,
      );
      setTimeout(() => window.close(), 2000);
    }
  }, [token]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-2">
          <p className="text-destructive text-lg font-medium">{t("auth.deleteCallback.failed")}</p>
          <p className="text-muted-foreground text-body">{t("auth.deleteCallback.retry")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-2">
        <Check className="h-12 w-12 text-primary mx-auto" />
        <p className="text-lg font-medium">{t("auth.deleteCallback.success")}</p>
        <p className="text-muted-foreground text-body">{t("auth.deleteCallback.closeWindow")}</p>
      </div>
    </div>
  );
}

export default function DeleteCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-background">
          <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
        </div>
      }
    >
      <DeleteCallbackContent />
    </Suspense>
  );
}
