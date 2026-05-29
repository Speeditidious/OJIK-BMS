"use client";

import { useDeferredValue, useCallback, useMemo, useState } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { Search } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { UserPublicRead } from "@/hooks/use-user-profile";
import { useRankingContributionRows } from "@/hooks/use-rankings";
import { useCalendarActivityDots } from "@/hooks/use-analysis";
import type {
  MyRankData,
  RankingTableConfig,
  RatingContributionScope,
  RatingContributionSortBy,
} from "@/lib/ranking-types";
import { fumenArtistText, fumenTitleText } from "@/lib/fumen-display";
import { cn } from "@/lib/utils";
import { RankingTableSelector } from "./RankingTableSelector";
import { RatingProfileHeader } from "./RatingProfileHeader";
import { ContributionTable } from "./ContributionTable";
import { SnapshotDatePicker } from "@/components/dashboard/SnapshotDatePicker";

const P_RATING_AS_OF = "rating_asof";

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
  enabled?: boolean;
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
  enabled = true,
}: RatingDetailSectionProps) {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const ratingAsOf = searchParams.get(P_RATING_AS_OF);

  const updateParams = useCallback((updates: Record<string, string | null>) => {
    const params = new URLSearchParams(searchParams.toString());
    for (const [k, v] of Object.entries(updates)) {
      if (v) params.set(k, v); else params.delete(k);
    }
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }, [searchParams, router, pathname]);

  const selectedTable = useMemo(
    () => tables.find((table) => table.slug === selectedTableSlug) ?? null,
    [selectedTableSlug, tables],
  );
  const [searchText, setSearchText] = useState("");
  const deferredSearch = useDeferredValue(searchText.trim());

  const [visibleCalendarFrom, setVisibleCalendarFrom] = useState<string | null>(null);
  const [visibleCalendarTo, setVisibleCalendarTo] = useState<string | null>(null);

  const activityDotsQuery = useCalendarActivityDots(
    visibleCalendarFrom,
    visibleCalendarTo,
    "all",
    userId ?? undefined,
    !!visibleCalendarFrom && !!visibleCalendarTo,
  );

  const playRecordDates = useMemo(
    () =>
      new Set(
        (activityDotsQuery.data?.data ?? [])
          .filter((day) => day.plays > 0)
          .map((day) => day.date),
      ),
    [activityDotsQuery.data],
  );

  const contributionQuery = useRankingContributionRows({
    tableSlug: myRank?.status === "ok" ? selectedTableSlug : null,
    metric: "rating",
    scope,
    sortBy,
    sortDir,
    query: scope === "all" ? deferredSearch : "",
    userId,
    enabled,
    asOf: ratingAsOf,
  });

  const displayedRankData = useMemo(() => {
    if (!ratingAsOf || !contributionQuery.data?.summary || myRank?.status !== "ok") return myRank;
    return {
      ...myRank,
      exp: contributionQuery.data.summary.exp,
      rating: contributionQuery.data.summary.rating,
      rating_norm: contributionQuery.data.summary.rating_norm,
      bms_force: contributionQuery.data.summary.rating_norm,
    };
  }, [ratingAsOf, contributionQuery.data?.summary, myRank]);
  const displayEntries = useMemo(() => {
    const entries = contributionQuery.data?.entries ?? [];
    if (scope !== "top" || !deferredSearch) return entries;

    const normalizedQuery = deferredSearch.toLocaleLowerCase();
    return entries.filter((entry) => {
      const title = fumenTitleText(entry.title, "").toLocaleLowerCase();
      const artist = fumenArtistText(entry.artist).toLocaleLowerCase();
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
        <>
          <RankingTableSelector
            tables={tables}
            selected={selectedTableSlug ?? tables[0].slug}
            onSelect={onSelectTable}
          />
          <div className="flex items-center gap-3">
            <SnapshotDatePicker
              selectedDate={ratingAsOf}
              onSelect={(date) => updateParams({ [P_RATING_AS_OF]: date })}
              playRecordDates={playRecordDates}
              onMonthChange={(from, to) => {
                setVisibleCalendarFrom(from);
                setVisibleCalendarTo(to);
              }}
            />
            {ratingAsOf && (
              <span className="text-caption text-muted-foreground">스냅샷: {ratingAsOf}</span>
            )}
          </div>
        </>
      ) : (
        <div className="rounded-xl border border-border bg-card/50 px-6 py-10 text-center text-body text-muted-foreground">
          {t("ranking.detail.noLinkedTables")}
        </div>
      )}

      <RatingProfileHeader
        profileUser={profileUser}
        data={displayedRankData}
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
                  {t("ranking.detail.all")}
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
                placeholder={t("ranking.detail.searchPlaceholder")}
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
                ? t("ranking.detail.noSearchResults")
                : scope === "all"
                  ? t("ranking.detail.noTableRecords")
                  : t("ranking.detail.noTopContributions")
            }
            allowSort={scope === "all"}
            sortBy={sortBy}
            sortDir={sortDir}
            onSortChange={handleSort}
            presentation={scope === "top" ? "rating-detail" : "default"}
            userId={userId ?? undefined}
          />
        </>
      ) : tables.length > 0 ? (
        <div className="rounded-xl border border-dashed border-border px-6 py-10 text-center text-body text-muted-foreground">
          {myRank?.status === "pending"
            ? t("ranking.detail.pending")
            : t("common.states.noData")}
        </div>
      ) : null}
    </div>
  );
}
