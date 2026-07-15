"use client";

import { useDeferredValue, useCallback, useMemo, useState } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { Calculator, Search } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { UserPublicRead } from "@/hooks/use-user-profile";
import { useRankingContributionRows } from "@/hooks/use-rankings";
import { useCalendarActivityDots } from "@/hooks/use-analysis";
import type {
  MyRankData,
  RankingContributionEntry,
  RankingTableConfig,
  RatingContributionScope,
  RatingContributionSortBy,
} from "@/lib/ranking-types";
import { fumenArtistText, fumenTitleText } from "@/lib/fumen-display";
import { getDisplayedRatingRankData } from "@/lib/rating-detail-display-core.mjs";
import { anyTextMatchesLooseQuery } from "@/lib/text-search-core.mjs";
import { cn } from "@/lib/utils";
import { RankingTableSelector } from "./RankingTableSelector";
import { RatingProfileHeader } from "./RatingProfileHeader";
import { ContributionTable } from "./ContributionTable";
import { RatingCalculatorDialog } from "./RatingCalculatorDialog";
import { RatingCalculatorPickerDialog } from "./RatingCalculatorPickerDialog";
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
  /** Whether the viewer is the profile owner — gates write actions (e.g. the calculator's readonly mode). */
  isOwner: boolean;
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
  isOwner,
}: RatingDetailSectionProps) {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const [calculatorOpen, setCalculatorOpen] = useState(false);
  const [calculatorEntry, setCalculatorEntry] = useState<RankingContributionEntry | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);

  const openCalculatorFor = useCallback((entry: RankingContributionEntry) => {
    setCalculatorEntry(entry);
    setCalculatorOpen(true);
  }, []);

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

  const displayedRankData = getDisplayedRatingRankData({
    ratingAsOf,
    myRank,
    contributionData: contributionQuery.data,
  });
  const displayEntries = useMemo(() => {
    const entries = contributionQuery.data?.entries ?? [];
    if (scope !== "top" || !deferredSearch) return entries;

    return entries.filter((entry) => {
      const title = fumenTitleText(entry.title, "");
      const artist = fumenArtistText(entry.artist);
      return anyTextMatchesLooseQuery([title, artist], deferredSearch);
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
            <div className="hidden md:flex md:items-center">
              <SnapshotDatePicker
                selectedDate={ratingAsOf}
                onSelect={(date) => updateParams({ [P_RATING_AS_OF]: date })}
                playRecordDates={playRecordDates}
                onMonthChange={(from, to) => {
                  setVisibleCalendarFrom(from);
                  setVisibleCalendarTo(to);
                }}
              />
            </div>
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

            <div className="flex items-center gap-2 md:ml-auto md:w-80">
              <button
                type="button"
                onClick={() => setPickerOpen(true)}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition-colors hover:border-primary hover:text-primary"
                aria-label={t("ranking.detail.calculator.pickerButtonAria")}
              >
                <Calculator className="h-4 w-4" />
              </button>
              <label className="relative block w-full">
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
            asOf={ratingAsOf}
            onOpenCalculator={openCalculatorFor}
          />
          {calculatorEntry && (
            <RatingCalculatorDialog
              open={calculatorOpen}
              onClose={() => setCalculatorOpen(false)}
              tableSlug={selectedTableSlug!}
              fumen={{
                sha256: calculatorEntry.sha256,
                md5: calculatorEntry.md5,
                level: calculatorEntry.level,
                title: calculatorEntry.title,
                artist: calculatorEntry.artist,
                symbol: calculatorEntry.symbol,
              }}
              current={{
                clearType: calculatorEntry.clear_type,
                rank: calculatorEntry.rank_grade,
                minBp: calculatorEntry.min_bp,
                rate: calculatorEntry.rate,
              }}
              clientType={calculatorEntry.client_types[0] ?? "beatoraja"}
              readonlyMode={!isOwner}
            />
          )}
          <RatingCalculatorPickerDialog
            open={pickerOpen}
            onClose={() => setPickerOpen(false)}
            tableSlug={selectedTableSlug}
            userId={userId}
            onSelectEntry={openCalculatorFor}
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
