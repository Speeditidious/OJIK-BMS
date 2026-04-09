"use client";

import { useState, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { Toaster } from "./toaster";
import { refreshTokens, getRefreshToken } from "@/lib/api";

export function Providers({ children }: { children: React.ReactNode }) {
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
        {children}
        <Toaster />
      </QueryClientProvider>
    </ThemeProvider>
  );
}
