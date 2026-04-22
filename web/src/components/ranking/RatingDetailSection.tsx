"use client";

import { useDeferredValue, useMemo, useState } from "react";
import { Search } from "lucide-react";
import type { UserPublicRead } from "@/hooks/use-user-profile";
import { useRankingContributionRows } from "@/hooks/use-rankings";
import type {
  MyRankData,
  RankingTableConfig,
  RatingContributionScope,
  RatingContributionSortBy,
} from "@/lib/ranking-types";
import { cn } from "@/lib/utils";
import { RankingTableSelector } from "./RankingTableSelector";
import { RatingProfileHeader } from "./RatingProfileHeader";
import { ContributionTable } from "./ContributionTable";

interface RatingDetailSectionProps {
  profileUser: UserPublicRead;
  tables: RankingTableConfig[];
  selectedTableSlug: string | null;
  onSelectTable: (slug: string) => void;
  userId?: string | null;
  myRank: MyRankData | null | undefined;
  myRankLoading: boolean;
  scope: RatingContributionScope;
  onScopeChange: (scope: RatingContributionScope) => void;
  sortBy: RatingContributionSortBy;
  sortDir: "asc" | "desc";
  onSortChange: (sortBy: RatingContributionSortBy, sortDir: "asc" | "desc") => void;
}

export function RatingDetailSection({
  profileUser,
  tables,
  selectedTableSlug,
  onSelectTable,
  userId,
  myRank,
  myRankLoading,
  scope,
  onScopeChange,
  sortBy,
  sortDir,
  onSortChange,
}: RatingDetailSectionProps) {
  const selectedTable = useMemo(
    () => tables.find((table) => table.slug === selectedTableSlug) ?? null,
    [selectedTableSlug, tables],
  );
  const [searchText, setSearchText] = useState("");
  const deferredSearch = useDeferredValue(searchText.trim());

  const contributionQuery = useRankingContributionRows({
    tableSlug: myRank?.status === "ok" ? selectedTableSlug : null,
    metric: "rating",
    scope,
    sortBy,
    sortDir,
    query: scope === "all" ? deferredSearch : "",
    userId,
  });
  const displayEntries = useMemo(() => {
    const entries = contributionQuery.data?.entries ?? [];
    if (scope !== "top" || !deferredSearch) return entries;

    const normalizedQuery = deferredSearch.toLocaleLowerCase();
    return entries.filter((entry) => {
      const title = entry.title.toLocaleLowerCase();
      const artist = entry.artist?.toLocaleLowerCase() ?? "";
      return title.includes(normalizedQuery) || artist.includes(normalizedQuery);
    });
  }, [contributionQuery.data?.entries, deferredSearch, scope]);

  function handleSort(nextSortBy: RatingContributionSortBy) {
    if (!selectedTableSlug || scope !== "all") return;
    if (nextSortBy === sortBy) {
      onSortChange(nextSortBy, sortDir === "asc" ? "desc" : "asc");
      return;
    }
    onSortChange(nextSortBy, "desc");
  }

  return (
    <div className="space-y-4">
      {tables.length > 0 ? (
        <RankingTableSelector
          tables={tables}
          selected={selectedTableSlug ?? tables[0].slug}
          onSelect={onSelectTable}
        />
      ) : (
        <div className="rounded-xl border border-border bg-card/50 px-6 py-10 text-center text-body text-muted-foreground">
          현재 랭킹 연동 난이도표가 없습니다.
        </div>
      )}

      <RatingProfileHeader
        profileUser={profileUser}
        data={myRank}
        isLoading={myRankLoading}
      />

      {myRank?.status === "ok" && selectedTable ? (
        <>
          <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr] md:items-center">
            <div className="hidden md:block" />
            <div className="flex justify-center">
              <div className="inline-flex rounded-lg border border-border bg-secondary p-0.5">
                <button
                  type="button"
                  onClick={() => {
                    onScopeChange("top");
                  }}
                  className={cn(
                    "px-4 py-1.5 rounded-md text-body font-medium transition-colors",
                    scope === "top" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  TOP {selectedTable.top_n}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    onScopeChange("all");
                  }}
                  className={cn(
                    "px-4 py-1.5 rounded-md text-body font-medium transition-colors",
                    scope === "all" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  전체
                </button>
              </div>
            </div>

            <label className="relative block w-full md:ml-auto md:w-80">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                value={searchText}
                onChange={(event) => {
                  setSearchText(event.target.value);
                }}
                placeholder="제목/아티스트 검색"
                className="w-full rounded-lg border border-border bg-card px-9 py-2 text-body outline-none transition-colors focus:border-primary"
              />
            </label>
          </div>

          <ContributionTable
            entries={scope === "top" ? displayEntries : (contributionQuery.data?.entries ?? [])}
            metric="rating"
            isLoading={contributionQuery.isLoading}
            totalEntries={scope === "top" ? displayEntries.length : (contributionQuery.data?.total_count ?? 0)}
            emptyMessage={
              deferredSearch
                ? "검색 결과가 없습니다."
                : scope === "all"
                  ? "해당 테이블 기록이 없습니다."
                  : "TOP 기여 차분이 없습니다."
            }
            allowSort={scope === "all"}
            sortBy={sortBy}
            sortDir={sortDir}
            onSortChange={handleSort}
            presentation={scope === "top" ? "rating-detail" : "default"}
          />
        </>
      ) : tables.length > 0 ? (
        <div className="rounded-xl border border-dashed border-border px-6 py-10 text-center text-body text-muted-foreground">
          {myRank?.status === "pending"
            ? "아직 랭킹 미반영 상태입니다. 계산이 반영되면 레이팅 상세 표가 표시됩니다."
            : "레이팅 상세를 표시할 플레이 데이터가 없습니다."}
        </div>
      ) : null}
    </div>
  );
}
