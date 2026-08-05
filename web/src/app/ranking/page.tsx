"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Trophy } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Navbar } from "@/components/layout/navbar";
import { NumberedPagination } from "@/components/common/NumberedPagination";
import { RankingTableSelector } from "@/components/ranking/RankingTableSelector";
import { RankingTypeToggle } from "@/components/ranking/RankingTypeToggle";
import { RankingTable } from "@/components/ranking/RankingTable";
import { MyRankCard } from "@/components/ranking/MyRankCard";
import { useRankingTables, useRankings, useMyRank } from "@/hooks/use-rankings";
import { useAuthStore } from "@/stores/auth";
import type { RankingType } from "@/lib/ranking-types";

const LIMIT = 50;

function RankingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuthStore();
  const { t } = useTranslation();

  const { data: tables, isLoading: tablesLoading } = useRankingTables();

  const tableSlug = searchParams.get("table") ?? tables?.[0]?.slug ?? null;
  const rawType = searchParams.get("type") as RankingType | null;
  const type: RankingType =
    rawType === "exp" ? rawType : "bmsforce";
  const page = Math.max(1, parseInt(searchParams.get("page") ?? "1", 10));

  const updateParams = useCallback(
    (updates: Record<string, string>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [k, v] of Object.entries(updates)) {
        params.set(k, v);
      }
      router.replace(`/ranking?${params.toString()}`);
    },
    [router, searchParams],
  );

  // Set default table slug on first load once tables are available
  useEffect(() => {
    if (!searchParams.get("table") && tables && tables.length > 0) {
      updateParams({ table: tables[0].slug });
    }
  }, [tables, searchParams, updateParams]);

  const { data: rankings, isLoading: rankingsLoading } = useRankings(
    tableSlug,
    type,
    page,
    LIMIT,
  );
  const { data: myRank, isLoading: myRankLoading } = useMyRank(
    user ? tableSlug : null,
  );

  const totalPages = rankings ? Math.ceil(rankings.total_count / LIMIT) : 1;

  return (
    <div className="container max-w-4xl py-6 space-y-5">
      {/* Title */}
      <div className="flex items-center gap-3">
        <Trophy className="h-7 w-7 text-primary" />
        <h1 className="text-3xl font-bold">{t("ranking.title")}</h1>
      </div>

      {/* Centered controls area */}
      <div className="flex flex-col items-center gap-3">
        {tablesLoading ? (
          <div className="flex gap-1">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="h-9 w-20 rounded-md bg-secondary animate-pulse"
              />
            ))}
          </div>
        ) : tables && tables.length > 0 ? (
          <RankingTableSelector
            tables={tables}
            selected={tableSlug ?? ""}
            onSelect={(slug) => updateParams({ table: slug, page: "1" })}
          />
        ) : (
          <p className="text-muted-foreground text-body">
            {t("ranking.noTables")}
          </p>
        )}

        <RankingTypeToggle
          type={type}
          onToggle={(t) => updateParams({ type: t, page: "1" })}
        />
      </div>

      {/* My rank card */}
      {user && (
        <MyRankCard
          data={myRank}
          type={type}
          isLoading={myRankLoading}
          isLoggedIn={true}
          tableSlug={tableSlug}
          user={user}
        />
      )}

      {/* Rankings table */}
      <RankingTable
        entries={rankings?.entries ?? []}
        type={type}
        myUserId={user?.id ?? null}
        isLoading={rankingsLoading}
      />

      {/* Pagination */}
      <NumberedPagination
        page={page}
        totalPages={totalPages}
        onChange={(p) => updateParams({ page: String(p) })}
      />
    </div>
  );
}

export default function RankingPage() {
  return (
    <>
      <Navbar />
      <main>
        <Suspense>
          <RankingContent />
        </Suspense>
      </main>
    </>
  );
}
