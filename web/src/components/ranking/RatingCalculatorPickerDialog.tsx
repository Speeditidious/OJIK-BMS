"use client";

import { useDeferredValue, useState } from "react";
import { useTranslation } from "react-i18next";
import { Search } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useRankingContributionRows } from "@/hooks/use-rankings";
import type { RankingContributionEntry, RatingContributionSortBy } from "@/lib/ranking-types";
import { ContributionTable } from "./ContributionTable";

export interface RatingCalculatorPickerDialogProps {
  open: boolean;
  onClose: () => void;
  /** Currently selected difficulty table's slug. Picker fetches every chart in this table (no scope gating). */
  tableSlug: string | null;
  userId?: string | null;
  /** Called with the picked chart's contribution row; caller opens `RatingCalculatorDialog` for it. */
  onSelectEntry: (entry: RankingContributionEntry) => void;
}

/**
 * Search/browse picker over *every* chart in the currently selected
 * difficulty table (including charts the user hasn't played — NOPLAY
 * baseline), independent of whatever scope ("top"/"all") the main
 * rating-detail table is currently showing.
 *
 * Clicking a chart's rating cell hands the entry off to the caller (which
 * opens `RatingCalculatorDialog` via `RatingDetailSection`'s existing
 * `openCalculatorFor`/`calculatorEntry`/`calculatorOpen` state) and closes
 * this picker.
 *
 * Layout mirrors `TableDetail.tsx`'s search + scrollable-list panel;
 * content reuses `ContributionTable` exactly like the "all" scope view in
 * `RatingDetailSection.tsx` — no extra virtualization dependency added,
 * since `ContributionTable` already self-virtualizes past 50 rows.
 */
export function RatingCalculatorPickerDialog({
  open,
  onClose,
  tableSlug,
  userId,
  onSelectEntry,
}: RatingCalculatorPickerDialogProps) {
  const { t } = useTranslation();
  const [searchText, setSearchText] = useState("");
  const deferredSearch = useDeferredValue(searchText.trim());
  const [sortBy, setSortBy] = useState<RatingContributionSortBy>("level");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const contributionQuery = useRankingContributionRows({
    tableSlug,
    metric: "rating",
    scope: "all",
    sortBy,
    sortDir,
    query: deferredSearch,
    userId,
    enabled: open && !!tableSlug,
  });

  function handleSort(nextSortBy: RatingContributionSortBy) {
    if (nextSortBy === sortBy) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortBy(nextSortBy);
    setSortDir("desc");
  }

  function handleOpenCalculator(entry: RankingContributionEntry) {
    onSelectEntry(entry);
    onClose();
  }

  const entries = contributionQuery.data?.entries ?? [];

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden bg-card p-0">
        <DialogHeader className="border-b border-border px-6 py-4">
          <DialogTitle className="text-lg font-semibold">
            {t("ranking.detail.calculator.pickerTitle")}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 space-y-3 overflow-y-auto px-6 py-4">
          <label className="relative block w-full">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder={t("ranking.detail.searchPlaceholder")}
              className="w-full rounded-lg border border-border bg-card px-9 py-2 text-body outline-none transition-colors focus:border-primary"
              autoFocus
            />
          </label>

          <ContributionTable
            entries={entries}
            metric="rating"
            isLoading={contributionQuery.isLoading}
            totalEntries={contributionQuery.data?.total_count ?? 0}
            emptyMessage={
              deferredSearch
                ? t("ranking.detail.noSearchResults")
                : t("ranking.detail.noTableRecords")
            }
            allowSort
            sortBy={sortBy}
            sortDir={sortDir}
            onSortChange={handleSort}
            presentation="default"
            userId={userId ?? undefined}
            onOpenCalculator={handleOpenCalculator}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
