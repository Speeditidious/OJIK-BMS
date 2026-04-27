"use client";

import { useState, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { Toaster } from "./toaster";
import { refreshTokens, getRefreshToken } from "@/lib/api";
import { RankingDisplayConfigProvider } from "@/components/ranking/RankingDisplayConfigProvider";

const CHUNK_LOAD_RETRY_KEY = "ojikbms:chunk-load-retry-at";
const CHUNK_LOAD_RETRY_WINDOW_MS = 60 * 1000;

function getErrorText(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }

  if (value instanceof Error) {
    return `${value.name} ${value.message} ${value.stack ?? ""}`;
  }

  if (value && typeof value === "object") {
    const candidate = value as { name?: unknown; message?: unknown; stack?: unknown };
    return [candidate.name, candidate.message, candidate.stack]
      .filter((part): part is string => typeof part === "string")
      .join(" ");
  }

  return "";
}

function isChunkLoadFailureText(text: string): boolean {
  const normalized = text.toLowerCase();

  return (
    normalized.includes("chunkloaderror") ||
    normalized.includes("failed to load chunk") ||
    normalized.includes("loading chunk") ||
    (normalized.includes("/_next/static/chunks/") &&
      (normalized.includes("failed") || normalized.includes("404")))
  );
}

function getFailedResourceUrl(event: Event): string {
  const target = event.target;

  if (target instanceof HTMLScriptElement) {
    return target.src;
  }

  if (target instanceof HTMLLinkElement) {
    return target.href;
  }

  return "";
}

function canRetryChunkLoad(): boolean {
  try {
    const lastRetryAt = Number(window.sessionStorage.getItem(CHUNK_LOAD_RETRY_KEY));
    const now = Date.now();

    if (Number.isFinite(lastRetryAt) && now - lastRetryAt < CHUNK_LOAD_RETRY_WINDOW_MS) {
      return false;
    }

    window.sessionStorage.setItem(CHUNK_LOAD_RETRY_KEY, String(now));
    return true;
  } catch {
    return false;
  }
}

function reloadOnceForChunkLoadFailure(): void {
  if (canRetryChunkLoad()) {
    window.location.reload();
  }
}

function useChunkLoadRecovery() {
  useEffect(() => {
    const handleError = (event: ErrorEvent | Event) => {
      const errorText =
        event instanceof ErrorEvent
          ? `${getErrorText(event.error)} ${event.message} ${event.filename}`
          : getFailedResourceUrl(event);
      const resourceUrl = getFailedResourceUrl(event);

      if (
        isChunkLoadFailureText(errorText) ||
        resourceUrl.includes("/_next/static/chunks/")
      ) {
        reloadOnceForChunkLoadFailure();
      }
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      if (isChunkLoadFailureText(getErrorText(event.reason))) {
        reloadOnceForChunkLoadFailure();
      }
    };

    window.addEventListener("error", handleError, true);
    window.addEventListener("unhandledrejection", handleUnhandledRejection);

    return () => {
      window.removeEventListener("error", handleError, true);
      window.removeEventListener("unhandledrejection", handleUnhandledRejection);
    };
  }, []);
}

export function Providers({ children }: { children: React.ReactNode }) {
  useChunkLoadRecovery();

  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,       // 1 minute global default
            gcTime: 10 * 60 * 1000,     // keep cache 10 minutes
            retry: 1,
          },
        },
      })
  );

  // Background token refresh: every 80 minutes (well before 2-hour expiry)
  useEffect(() => {
    const id = setInterval(() => {
      if (getRefreshToken()) refreshTokens();
    }, 80 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
      <QueryClientProvider client={queryClient}>
        <RankingDisplayConfigProvider>
          {children}
        </RankingDisplayConfigProvider>
        <Toaster />
      </QueryClientProvider>
    </ThemeProvider>
  );
}
