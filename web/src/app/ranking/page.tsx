"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Trophy } from "lucide-react";
import { Navbar } from "@/components/layout/navbar";
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

  const { data: tables, isLoading: tablesLoading } = useRankingTables();

  const tableSlug = searchParams.get("table") ?? tables?.[0]?.slug ?? null;
  const rawType = searchParams.get("type") as RankingType | null;
  const type: RankingType =
    rawType === "bmsforce" ? rawType : "exp";
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
        <h1 className="text-3xl font-bold">랭킹</h1>
      </div>

      {/* 중앙정렬 컨트롤 영역 */}
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
            현재 랭킹에 등록된 난이도표가 없습니다.
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
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <button
            disabled={page <= 1}
            onClick={() => updateParams({ page: String(page - 1) })}
            className="px-3 py-1.5 rounded border border-border text-body disabled:opacity-40 hover:bg-secondary transition-colors"
          >
            ←
          </button>
          {Array.from({ length: Math.min(totalPages, 7) }).map((_, i) => {
            const p = i + 1;
            return (
              <button
                key={p}
                onClick={() => updateParams({ page: String(p) })}
                className={`px-3 py-1.5 rounded border border-border text-body transition-colors ${
                  p === page
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-secondary"
                }`}
              >
                {p}
              </button>
            );
          })}
          {totalPages > 7 && (
            <>
              <span className="text-muted-foreground">…</span>
              <button
                onClick={() => updateParams({ page: String(totalPages) })}
                className={`px-3 py-1.5 rounded border border-border text-body transition-colors ${
                  page === totalPages
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-secondary"
                }`}
              >
                {totalPages}
              </button>
            </>
          )}
          <button
            disabled={page >= totalPages}
            onClick={() => updateParams({ page: String(page + 1) })}
            className="px-3 py-1.5 rounded border border-border text-body disabled:opacity-40 hover:bg-secondary transition-colors"
          >
            →
          </button>
        </div>
      )}
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
