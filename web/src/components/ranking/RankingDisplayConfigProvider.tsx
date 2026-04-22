"use client";

import { createContext, useContext } from "react";
import { useRankingDisplayConfig } from "@/hooks/use-ranking-display-config";
import type { BmsforceEmblem } from "@/lib/bmsforce-emblem";

/** Context value: the resolved BMSFORCE emblems array. */
export const BmsforceEmblemsContext = createContext<BmsforceEmblem[]>([]);

/**
 * Fetches ranking display config once and provides BMSFORCE emblems
 * via React Context. Mount this at the app root to avoid N × useQuery
 * subscriptions from individual <BmsforceValue /> instances.
 */
export function RankingDisplayConfigProvider({ children }: { children: React.ReactNode }) {
  const { data } = useRankingDisplayConfig();
  const emblems = data?.bmsforce_emblems ?? [];
  return (
    <BmsforceEmblemsContext.Provider value={emblems}>
      {children}
    </BmsforceEmblemsContext.Provider>
  );
}

/** Consume the BMSFORCE emblems array from context. */
export function useBmsforceEmblems(): BmsforceEmblem[] {
  return useContext(BmsforceEmblemsContext);
}
