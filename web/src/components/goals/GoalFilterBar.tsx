"use client";

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, ChevronDown, ChevronUp, RotateCcw, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GoalFilterAxis } from "@/components/goals/GoalFilterAxis";
import type { GoalRecord } from "@/hooks/use-goals";
import type { AxisFilter, GoalFilter, GoalTable } from "@/lib/goal-filter-core";
import {
  activeFilterCount,
  emptyGoalFilter,
  filterGoals,
  goalFacetCounts,
  goalFilterOptions,
  splitGoalsByAxis,
} from "@/lib/goal-filter-core";

interface GoalFilterBarProps {
  /** The unfiltered goal list this bar derives its options and counts from. */
  goals: GoalRecord[];
  /** Server-ordered difficulty tables referenced by `goals`. */
  tables: GoalTable[];
  filter: GoalFilter;
  onFilterChange: (next: GoalFilter) => void;
  /** The achieved-date range only makes sense on the achieved tab. */
  showAchievedRange: boolean;
}

/**
 * Collapsible filter panel over a goal list, split into a chart axis and a
 * course axis that narrow their own goals independently.
 */
export function GoalFilterBar({
  goals,
  tables,
  filter,
  onFilterChange,
  showAchievedRange,
}: GoalFilterBarProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  const options = useMemo(() => goalFilterOptions(goals, tables), [goals, tables]);
  const counts = useMemo(() => goalFacetCounts(goals, filter, options), [goals, filter, options]);
  const activeCount = activeFilterCount(filter, options);

  // Per-axis pass counts for the column headers.
  const matched = useMemo(() => splitGoalsByAxis(filterGoals(goals, filter)), [goals, filter]);

  function patchAxis(axis: "chart" | "course", next: AxisFilter) {
    onFilterChange({ ...filter, [axis]: next });
  }

  function toggleLevelDisplayPrefs() {
    onFilterChange({ ...filter, applyLevelDisplayPrefs: !filter.applyLevelDisplayPrefs });
  }

  return (
    <div className="space-y-2">
      <div className="flex items-stretch gap-2">
        <Button
          variant={activeCount > 0 ? "default" : "outline"}
          size="lg"
          className="flex-1 justify-center gap-2 font-semibold"
          onClick={() => setIsOpen((open) => !open)}
        >
          <SlidersHorizontal className="h-4 w-4 shrink-0" />
          {t("goals.filter.title")}
          {activeCount > 0 && (
            <span className="font-normal opacity-80">
              {t("goals.filter.activeCount", { count: activeCount })}
            </span>
          )}
          {isOpen ? (
            <ChevronUp className="h-3.5 w-3.5 shrink-0" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5 shrink-0" />
          )}
        </Button>
        <Button
          variant="outline"
          size="lg"
          className="shrink-0 gap-1.5"
          onClick={() => onFilterChange(emptyGoalFilter())}
          disabled={activeCount === 0}
        >
          <RotateCcw className="h-3.5 w-3.5" />
          {t("goals.filter.reset")}
        </Button>
      </div>

      {isOpen && (
        // Recessed surface: the panel reads as a tool, the goal cards below as
        // content. `bg-background` sits below the surrounding card's `bg-card`
        // in both themes, so the contrast holds without a dark-only class.
        <div className="rounded-lg border border-border bg-background p-4 shadow-inner">
          <button
            type="button"
            aria-pressed={filter.applyLevelDisplayPrefs}
            onClick={toggleLevelDisplayPrefs}
            className="mb-4 inline-flex items-center gap-2 rounded-md border border-border bg-card/50 px-2.5 py-1.5 text-label font-semibold text-foreground transition-colors hover:bg-secondary/60"
          >
            <span>{t("goals.filter.applyLevelDisplayPrefs")}</span>
            <span
              className={
                filter.applyLevelDisplayPrefs
                  ? "inline-flex h-4 w-4 items-center justify-center rounded-sm bg-primary text-primary-foreground"
                  : "inline-flex h-4 w-4 items-center justify-center rounded-sm border border-muted-foreground/40"
              }
            >
              {filter.applyLevelDisplayPrefs && <Check className="h-3 w-3" />}
            </span>
          </button>
          <div className="flex flex-col gap-4 lg:flex-row lg:gap-0">
            <GoalFilterAxis
              axis="chart"
              filter={filter.chart}
              options={options.chart}
              counts={counts.chart}
              matchedCount={matched.chart.length}
              onFilterChange={(next) => patchAxis("chart", next)}
              showAchievedRange={showAchievedRange}
            />
            <div className="hidden w-px shrink-0 bg-border lg:mx-4 lg:block" />
            <div className="h-px w-full bg-border lg:hidden" />
            <GoalFilterAxis
              axis="course"
              filter={filter.course}
              options={options.course}
              counts={counts.course}
              matchedCount={matched.course.length}
              onFilterChange={(next) => patchAxis("course", next)}
              showAchievedRange={showAchievedRange}
            />
          </div>
        </div>
      )}
    </div>
  );
}
