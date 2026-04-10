"use client";

import { useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Check } from "lucide-react";

function DeleteCallbackContent() {
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
          <p className="text-destructive text-lg font-medium">인증에 실패했습니다</p>
          <p className="text-muted-foreground text-body">이 창을 닫고 다시 시도해주세요.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-2">
        <Check className="h-12 w-12 text-primary mx-auto" />
        <p className="text-lg font-medium">인증이 완료되었습니다</p>
        <p className="text-muted-foreground text-body">이 창은 자동으로 닫힙니다.</p>
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
