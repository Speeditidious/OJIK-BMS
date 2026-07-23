"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Check, ChevronLeft, Loader2, Music2, Search, Trophy, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Pagination } from "@/components/common/Pagination";
import { TableLevelBadges } from "@/components/common/TableLevelBadges";
import { CLEAR_TYPE_LABELS } from "@/components/charts/ClearDistributionChart";
import {
  RatingCalculatorDialog,
  RATING_CLEAR_TYPES,
  RATING_RANKS,
  getClientLabels,
  minRateForRank,
  normalizeClearForRating,
  rankGradeFromRate,
  sanitizeBpInput,
  sanitizeRateInput,
} from "@/components/ranking/RatingCalculatorDialog";
import { useRankingTables, useRankingContributionRows } from "@/hooks/use-rankings";
import { useFavoriteTables } from "@/hooks/use-tables";
import {
  useCreateGoal,
  useGoalBaseline,
  useGoals,
  useTargetCourses,
  type GoalBaseline,
  type TargetCourse,
} from "@/hooks/use-goals";
import { useFumensList } from "@/hooks/use-fumens-list";
import type { GoalDraft } from "@/lib/goal-types";
import { validateGoalTarget } from "@/lib/goal-validation-core.mjs";
import { formatGoalValidationErrors } from "@/lib/goal-validation-message";
import { anyTextMatchesLooseQuery } from "@/lib/text-search-core.mjs";
import { formatRatePercent } from "@/lib/rate-format";
import { formatTableLevelWithSymbolForDisplay } from "@/lib/table-level-display";
import { CLEAR_ROW_CLASS, CLEAR_ROW_STATIC_CLASS } from "@/lib/fumen-table-utils";
import { displayClearType } from "@/lib/clear-type-display";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { DifficultyTable, DifficultyTableDetail, FumenListItem, FumenSearchField, TableFumen } from "@/types";

const CLIENT_TYPES = ["lr2", "beatoraja"] as const;
const CLIENT_LABELS: Record<string, string> = { lr2: "LR2", beatoraja: "Beatoraja" };

type ChartScope = "rating" | "table" | "all";
type CourseScope = "supported" | "table" | "all";
type GoalSearchField = "title_artist" | "title" | "artist" | "level" | "clear" | "bp" | "rate" | "rank" | "badge" | "name" | "active";
type ChartGoalSortKey = "title" | "clear" | "bp" | "rate" | "rank";
type CourseGoalSortKey = "badge" | "name" | "clear" | "rank" | "active";
type SortDir = "asc" | "desc";

const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
const COURSE_GOAL_CLEAR_TYPES = [0, 1, 4, 5, 6, 7, 8, 9];

type Step =
  | "type"
  | "table"
  | "chart-pick"
  | "chart-table-choice"
  | "adjust-chart"
  | "adjust-chart-no-rating"
  | "course-pick"
  | "adjust-course"
  | "confirm";

interface CourseAdjust {
  clearType: number;
  minBp: number | null;
  rate: number | null;
  rank: string;
}

/** The subset of CourseAdjust fields the user actually changed vs. baseline — mirrors the calculator's changed-only filtering (Task 7). */
interface CourseAdjustDiff {
  clearType: number | null;
  minBp: number | null;
  rate: number | null;
  rank: string | null;
}

interface GoalSetupDialogProps {
  open: boolean;
  onClose: () => void;
  /** Prefilled draft from the rating calculator's "set as goal" action (plan §3.4-2) — skips straight to the confirm step. */
  initialDraft?: GoalDraft | null;
}

/**
 * Goal ("quest") setup wizard (plan §3.4). Two entry shapes:
 *  - Full flow from the dashboard's goal section: type -> table/course pick -> adjust -> confirm.
 *  - Prefilled from the rating calculator's onSetGoal: opens directly at confirm.
 *
 * The chart-adjustment step reuses `RatingCalculatorDialog` itself (its `onSetGoal`
 * callback produces the same `GoalDraft` shape either way) — only one Radix Dialog
 * is ever "open" at a time; the wizard's own Dialog closes while the calculator's is open.
 */
export function GoalSetupDialog({ open, onClose, initialDraft }: GoalSetupDialogProps) {
  const { t } = useTranslation();
  const [step, setStep] = useState<Step>("type");
  const [selectedTableSlug, setSelectedTableSlug] = useState<string | null>(null);
  const [chartSearch, setChartSearch] = useState("");
  const [courseSearch, setCourseSearch] = useState("");
  const [chartSearchField, setChartSearchField] = useState<GoalSearchField>("title_artist");
  const [courseSearchField, setCourseSearchField] = useState<GoalSearchField>("name");
  const [chartLevelFilter, setChartLevelFilter] = useState<string | null>(null);
  const [chartSortKey, setChartSortKey] = useState<ChartGoalSortKey>("title");
  const [chartSortDir, setChartSortDir] = useState<SortDir>("asc");
  const [courseSortKey, setCourseSortKey] = useState<CourseGoalSortKey>("badge");
  const [courseSortDir, setCourseSortDir] = useState<SortDir>("asc");
  const [chartScope, setChartScope] = useState<ChartScope>("table");
  const [courseScope, setCourseScope] = useState<CourseScope>("supported");
  const [selectedCourseTableSlug, setSelectedCourseTableSlug] = useState<string | null>(null);
  const [allSongsSearch, setAllSongsSearch] = useState("");
  const [allSongsSearchField, setAllSongsSearchField] = useState<GoalSearchField>("title_artist");
  const [allSongsPage, setAllSongsPage] = useState(1);
  const [multiTableCandidate, setMultiTableCandidate] = useState<{
    item: FumenListItem;
    candidates: { slug: string; displayName: string; level: string; symbol: string }[];
  } | null>(null);
  /** Which flow led into "adjust-chart" (the calculator) — determines where its close button returns to. */
  const [chartAdjustOrigin, setChartAdjustOrigin] = useState<"table-pick" | "all-songs">("table-pick");

  const [pendingChart, setPendingChart] = useState<GoalDraft | null>(null);
  const [chartPickCurrent, setChartPickCurrent] = useState<{
    fumen: GoalDraft["fumen"];
    ratingTableOptions?: { slug: string; displayName: string; level: string; symbol: string }[];
    current: { clearType: number | null; rank: string | null; minBp: number | null; rate: number | null };
    defaultClientType: string;
  } | null>(null);

  const [pendingCourseTarget, setPendingCourseTarget] = useState<TargetCourse | null>(null);
  const [courseAdjust, setCourseAdjust] = useState<CourseAdjust>({ clearType: 1, minBp: null, rate: null, rank: "F" });
  const [courseAdjustClientType, setCourseAdjustClientType] = useState<string>("beatoraja");
  const [noRatingAdjust, setNoRatingAdjust] = useState<CourseAdjust>({ clearType: 1, minBp: null, rate: null, rank: "F" });
  const [pendingCourse, setPendingCourse] = useState<
    (CourseAdjustDiff & { course: TargetCourse; clientType: string }) | null
  >(null);

  const [clientType, setClientType] = useState<string>("beatoraja");
  const [serverError, setServerError] = useState<string | null>(null);

  const activeGoalsQuery = useGoals("active", open);
  const defaultClientType = activeGoalsQuery.data?.default_client_type ?? null;

  const createGoal = useCreateGoal();

  const courseAdjustBaselineQuery = useGoalBaseline({
    goalType: "course",
    clientType: pendingCourseTarget ? courseAdjustClientType : null,
    courseId: pendingCourseTarget?.course_id,
    enabled: step === "adjust-course" && !!pendingCourseTarget,
  });

  // Same source `baselineQuery` uses at confirm — keeps the no-rating adjust step's clamp/seed
  // values consistent with what confirm later re-validates against (avoids a value the adjust
  // panel accepted being silently rejected at confirm due to a different baseline source).
  const noRatingBaselineQuery = useGoalBaseline({
    goalType: "chart",
    clientType: chartPickCurrent ? chartPickCurrent.defaultClientType : null,
    fumenSha256: chartPickCurrent?.fumen.sha256,
    fumenMd5: chartPickCurrent?.fumen.md5,
    enabled: step === "adjust-chart-no-rating" && !!chartPickCurrent,
  });

  // Reset all wizard state whenever the dialog (re)opens.
  useEffect(() => {
    if (!open) return;
    setServerError(null);
    if (initialDraft) {
      setPendingChart(initialDraft);
      setPendingCourseTarget(null);
      setPendingCourse(null);
      setCourseAdjustClientType(defaultClientType || "beatoraja");
      setClientType(initialDraft.clientType || defaultClientType || "beatoraja");
      setStep("confirm");
    } else {
      setStep("type");
      setSelectedTableSlug(null);
      setChartSearch("");
      setCourseSearch("");
      setChartSearchField("title_artist");
      setCourseSearchField("name");
      setChartLevelFilter(null);
      setChartSortKey("title");
      setChartSortDir("asc");
      setCourseSortKey("badge");
      setCourseSortDir("asc");
      setPendingChart(null);
      setChartPickCurrent(null);
      setPendingCourseTarget(null);
      setPendingCourse(null);
      setCourseAdjustClientType(defaultClientType || "beatoraja");
      setChartScope("rating");
      setCourseScope("supported");
      setSelectedCourseTableSlug(null);
      setAllSongsSearch("");
      setAllSongsSearchField("title_artist");
      setAllSongsPage(1);
      setMultiTableCandidate(null);
      setNoRatingAdjust({ clearType: 1, minBp: null, rate: null, rank: "F" });
      setChartAdjustOrigin("table-pick");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initialDraft]);

  useEffect(() => {
    if (step !== "adjust-course" || !courseAdjustBaselineQuery.data) return;
    const b = courseAdjustBaselineQuery.data;
    setCourseAdjust({
      clearType: normalizeClearForRating(b.clear_type),
      minBp: b.min_bp,
      rate: b.rate,
      rank: b.rank ?? rankGradeFromRate(b.rate),
    });
    // Only re-seed when a fresh baseline arrives for a newly-picked course, not on every
    // background refetch of the same query.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courseAdjustBaselineQuery.data, pendingCourseTarget?.course_id]);

  useEffect(() => {
    if (step !== "adjust-chart-no-rating" || !noRatingBaselineQuery.data) return;
    const b = noRatingBaselineQuery.data;
    setNoRatingAdjust({
      clearType: normalizeClearForRating(b.clear_type),
      minBp: b.min_bp,
      rate: b.rate,
      rank: b.rank ?? rankGradeFromRate(b.rate),
    });
    // Only re-seed when a fresh baseline arrives for a newly-picked chart, not on every
    // background refetch of the same query.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [noRatingBaselineQuery.data, chartPickCurrent?.fumen.sha256, chartPickCurrent?.fumen.md5]);

  const rankingTablesQuery = useRankingTables();
  const favoriteTablesQuery = useFavoriteTables();

  const allTablesQuery = useQuery<DifficultyTable[]>({
    queryKey: ["tables"],
    queryFn: () => api.get<DifficultyTable[]>("/tables/"),
    staleTime: 5 * 60 * 1000,
    enabled: step === "table" || step === "chart-pick" || step === "course-pick",
  });
  const allTables = useMemo(() => allTablesQuery.data ?? [], [allTablesQuery.data]);
  const favoriteTables = (favoriteTablesQuery.data ?? []) as DifficultyTable[];
  const tableBySlug = useMemo(() => {
    return new Map(allTables.filter((table) => table.slug).map((table) => [table.slug!, table]));
  }, [allTables]);
  const tableSymbolById = useMemo(() => new Map(allTables.map((table) => [table.id, table.symbol ?? ""])), [allTables]);

  /** table_id -> {slug, symbol, hasRating}, merging /rankings/tables (has_rating, slug) with /tables/ (symbol). */
  const tableLookup = useMemo(() => {
    const symbolById = new Map((allTablesQuery.data ?? []).map((t) => [t.id, t.symbol ?? ""]));
    const map = new Map<string, { slug: string; symbol: string; hasRating: boolean; displayName: string }>();
    for (const table of rankingTablesQuery.data ?? []) {
      map.set(table.table_id, {
        slug: table.slug,
        symbol: symbolById.get(table.table_id) ?? "",
        hasRating: table.has_rating,
        displayName: table.display_name,
      });
    }
    return map;
  }, [rankingTablesQuery.data, allTablesQuery.data]);

  const allSongsQuery = useFumensList({
    field: allSongsSearchField as FumenSearchField,
    q: allSongsSearch,
    page: allSongsPage,
    limit: 20,
    enabled: step === "table" && chartScope === "all",
  });
  const allSongsTotalPages = allSongsQuery.data ? Math.max(1, Math.ceil(allSongsQuery.data.total / allSongsQuery.data.limit)) : 1;

  const chartRowsQuery = useRankingContributionRows({
    tableSlug: selectedTableSlug,
    metric: "rating",
    scope: "all",
    sortBy: "value",
    sortDir: "desc",
    enabled: step === "chart-pick" && !!selectedTableSlug && (rankingTablesQuery.data ?? []).some((table) => table.slug === selectedTableSlug && table.has_rating),
  });
  const selectedChartTable = selectedTableSlug ? tableBySlug.get(selectedTableSlug) ?? null : null;
  const selectedChartTableHasRating = (rankingTablesQuery.data ?? []).some((table) => table.slug === selectedTableSlug && table.has_rating);
  const selectedChartTableDetailQuery = useQuery<DifficultyTableDetail>({
    queryKey: ["table", selectedChartTable?.id],
    queryFn: () => api.get<DifficultyTableDetail>(`/tables/${selectedChartTable!.id}`),
    enabled: step === "chart-pick" && !!selectedChartTable?.id,
    staleTime: 5 * 60 * 1000,
  });
  const tableSongsQuery = useQuery<TableFumen[]>({
    queryKey: ["table-songs", selectedChartTable?.id],
    queryFn: () => api.get<TableFumen[]>(`/tables/${selectedChartTable!.id}/songs`),
    enabled: step === "chart-pick" && !!selectedChartTable?.id && !selectedChartTableHasRating,
    staleTime: 5 * 60 * 1000,
  });
  const filteredChartRows = useMemo(() => {
    const entries = chartRowsQuery.data?.entries ?? [];
    return sortChartGoalRows(
      filterChartGoalRows(entries, chartSearch, chartSearchField)
        .filter((entry) => chartLevelFilter == null || entry.level === chartLevelFilter),
      chartSortKey,
      chartSortDir,
    );
  }, [chartLevelFilter, chartRowsQuery.data, chartSearch, chartSearchField, chartSortDir, chartSortKey]);
  const filteredTableSongs = useMemo(() => {
    const entries = tableSongsQuery.data ?? [];
    return sortTableFumensForGoal(
      filterTableFumensForGoal(entries, chartSearch, chartSearchField)
        .filter((entry) => chartLevelFilter == null || entry.level === chartLevelFilter),
      chartSortKey,
      chartSortDir,
    );
  }, [chartLevelFilter, chartSearch, chartSearchField, chartSortDir, chartSortKey, tableSongsQuery.data]);
  const chartLevelCounts = useMemo(() => {
    const counts = new Map<string, number>();
    const source = selectedChartTableHasRating ? (chartRowsQuery.data?.entries ?? []) : (tableSongsQuery.data ?? []);
    for (const row of source) counts.set(row.level, (counts.get(row.level) ?? 0) + 1);
    const levelOrder = selectedChartTableDetailQuery.data?.level_order ?? [];
    return Array.from(counts.entries()).sort(([left], [right]) => {
      const leftIndex = levelOrder.indexOf(left);
      const rightIndex = levelOrder.indexOf(right);
      if (leftIndex !== -1 || rightIndex !== -1) {
        return (leftIndex === -1 ? 9999 : leftIndex) - (rightIndex === -1 ? 9999 : rightIndex);
      }
      return collator.compare(left, right);
    });
  }, [chartRowsQuery.data?.entries, selectedChartTableDetailQuery.data?.level_order, selectedChartTableHasRating, tableSongsQuery.data]);

  useEffect(() => {
    if (step !== "chart-pick" || chartLevelFilter != null || chartLevelCounts.length === 0) return;
    setChartLevelFilter(chartLevelCounts[0][0]);
  }, [chartLevelCounts, chartLevelFilter, step]);

  const targetCoursesQuery = useTargetCourses(step === "course-pick");
  const displayCourses = useMemo(() => dedupeGoalCourses(targetCoursesQuery.data?.courses ?? []), [targetCoursesQuery.data?.courses]);
  const allScopeCourses = useMemo(() => {
    return sortCourses(filterCoursesForGoal(displayCourses, courseSearch, courseSearchField), courseSortKey, courseSortDir);
  }, [courseSearch, courseSearchField, courseSortDir, courseSortKey, displayCourses]);
  const supportedCourseTableSlugs = useMemo(() => {
    const slugs = new Set<string>();
    for (const course of displayCourses) {
      for (const slug of supportedSlugsForCourse(course)) slugs.add(slug);
    }
    return slugs;
  }, [displayCourses]);
  const supportedCourseTables = useMemo(() => {
    const rankingOrder = new Map((rankingTablesQuery.data ?? []).map((table, index) => [table.slug, index]));
    return Array.from(supportedCourseTableSlugs)
      .map((slug) => tableBySlug.get(slug))
      .filter((table): table is DifficultyTable => table != null)
      .sort((left, right) => (rankingOrder.get(left.slug ?? "") ?? 9999) - (rankingOrder.get(right.slug ?? "") ?? 9999));
  }, [rankingTablesQuery.data, supportedCourseTableSlugs, tableBySlug]);
  const courseTablesForScope = courseScope === "supported" ? supportedCourseTables : allTables;
  const supportedCourseCountBySlug = useMemo(() => {
    const counts = new Map<string, { active: number; total: number }>();
    for (const course of displayCourses) {
      for (const slug of supportedSlugsForCourse(course)) {
        const next = counts.get(slug) ?? { active: 0, total: 0 };
        next.total += 1;
        if (course.is_active) next.active += 1;
        counts.set(slug, next);
      }
    }
    return counts;
  }, [displayCourses]);
  const tableCourseCountBySlug = useMemo(() => {
    const counts = new Map<string, { active: number; total: number }>();
    for (const course of displayCourses) {
      if (!course.table_slug) continue;
      const next = counts.get(course.table_slug) ?? { active: 0, total: 0 };
      next.total += 1;
      if (course.is_active) next.active += 1;
      counts.set(course.table_slug, next);
    }
    return counts;
  }, [displayCourses]);
  const selectedCourseTable = selectedCourseTableSlug ? tableBySlug.get(selectedCourseTableSlug) ?? null : null;
  const tableScopedCourses = useMemo(() => {
    if (!selectedCourseTableSlug) return [];
    const filtered = displayCourses.filter((course) =>
      courseScope === "supported"
        ? supportedSlugsForCourse(course).includes(selectedCourseTableSlug)
        : course.table_slug === selectedCourseTableSlug,
    );
    return sortCourses(filterCoursesForGoal(filtered, courseSearch, courseSearchField), courseSortKey, courseSortDir);
  }, [courseScope, courseSearch, courseSearchField, courseSortDir, courseSortKey, displayCourses, selectedCourseTableSlug]);

  const goalType: "chart" | "course" | null = pendingChart ? "chart" : pendingCourse ? "course" : null;

  const baselineQuery = useGoalBaseline({
    goalType: goalType ?? "chart",
    clientType: step === "confirm" ? clientType : null,
    fumenSha256: pendingChart?.fumen.sha256,
    fumenMd5: pendingChart?.fumen.md5,
    courseId: pendingCourse?.course.course_id,
    enabled: step === "confirm" && !!goalType,
  });

  const target = useMemo(() => {
    if (pendingChart) {
      return { clearType: pendingChart.clearType, minBp: pendingChart.minBp, rank: pendingChart.rank, rate: pendingChart.rate };
    }
    if (pendingCourse) {
      return { clearType: pendingCourse.clearType, minBp: pendingCourse.minBp, rank: pendingCourse.rank, rate: pendingCourse.rate };
    }
    return { clearType: null, minBp: null, rank: null, rate: null };
  }, [pendingChart, pendingCourse]);

  const validation = useMemo(() => {
    if (!baselineQuery.data) return null;
    return validateGoalTarget(baselineQuery.data, target);
  }, [baselineQuery.data, target]);

  function handleClose() {
    onClose();
  }

  function handleSelectTable(slug: string) {
    setSelectedTableSlug(slug);
    setChartSearch("");
    setChartSearchField("title_artist");
    setChartLevelFilter(null);
    setChartSortKey("title");
    setChartSortDir("asc");
    setStep("chart-pick");
  }

  function handleSelectChart(entry: (typeof filteredChartRows)[number]) {
    const fumen: GoalDraft["fumen"] = {
      sha256: entry.sha256,
      md5: entry.md5,
      level: entry.level,
      title: entry.title,
      artist: entry.artist,
      symbol: entry.symbol,
    };
    setChartPickCurrent({
      fumen,
      current: { clearType: entry.clear_type, rank: entry.rank_grade, minBp: entry.min_bp, rate: entry.rate },
      defaultClientType: entry.client_types[0] ?? defaultClientType ?? "beatoraja",
    });
    setChartAdjustOrigin("table-pick");
    setStep("adjust-chart");
  }

  function handleSelectTableSong(entry: TableFumen) {
    setChartPickCurrent({
      fumen: {
        sha256: entry.sha256,
        md5: entry.md5,
        level: entry.level,
        title: entry.title ?? "",
        artist: entry.artist,
        symbol: selectedChartTable?.symbol ?? undefined,
      },
      current: {
        clearType: entry.user_score?.best_clear_type ?? null,
        rank: entry.user_score?.rank ?? null,
        minBp: entry.user_score?.best_min_bp ?? null,
        rate: entry.user_score?.rate ?? null,
      },
      defaultClientType: entry.user_score?.client_type ?? defaultClientType ?? "beatoraja",
    });
    setSelectedTableSlug(selectedChartTable?.slug ?? null);
    setChartAdjustOrigin("table-pick");
    setStep("adjust-chart");
  }

  function handleSelectChartFromAllSongs(item: FumenListItem) {
    const ratingCandidates = (item.table_entries ?? [])
      .map((entry) => {
        const info = tableLookup.get(entry.table_id);
        if (!info || !info.hasRating) return null;
        return { slug: info.slug, displayName: info.displayName, level: entry.level, symbol: info.symbol };
      })
      .filter((c): c is { slug: string; displayName: string; level: string; symbol: string } => c !== null);

    const baseFumen = {
      sha256: item.sha256,
      md5: item.md5,
      title: item.title ?? "",
      artist: item.artist,
      levels: (item.table_entries ?? [])
        .filter((entry) => entry.level)
        .map((entry) => ({
          symbol: tableLookup.get(entry.table_id)?.symbol ?? tableSymbolById.get(entry.table_id) ?? "",
          slug: tableLookup.get(entry.table_id)?.slug ?? "",
          level: entry.level,
        })),
    };
    const baseCurrent = {
      clearType: item.user_score?.best_clear_type ?? null,
      rank: item.user_score?.rank ?? null,
      minBp: item.user_score?.best_min_bp ?? null,
      rate: item.user_score?.rate ?? null,
    };
    const clientTypeForItem = item.user_score?.client_type ?? defaultClientType ?? "beatoraja";

    if (ratingCandidates.length === 0) {
      const firstEntry = item.table_entries?.[0];
      setChartPickCurrent({
        fumen: {
          ...baseFumen,
          level: firstEntry?.level ?? "",
          symbol: firstEntry ? tableSymbolById.get(firstEntry.table_id) : undefined,
        },
        current: baseCurrent,
        defaultClientType: clientTypeForItem,
      });
      setSelectedTableSlug(null);
      setChartAdjustOrigin("all-songs");
      setStep("adjust-chart");
      return;
    }

    if (ratingCandidates.length === 1) {
      const only = ratingCandidates[0];
      setChartPickCurrent({
        fumen: { ...baseFumen, level: only.level, symbol: only.symbol },
        ratingTableOptions: ratingCandidates,
        current: baseCurrent,
        defaultClientType: clientTypeForItem,
      });
      setSelectedTableSlug(only.slug);
      setChartAdjustOrigin("all-songs");
      setStep("adjust-chart");
      return;
    }

    const first = ratingCandidates[0];
    setChartPickCurrent({
      fumen: { ...baseFumen, level: first.level, symbol: first.symbol },
      ratingTableOptions: ratingCandidates,
      current: baseCurrent,
      defaultClientType: clientTypeForItem,
    });
    setSelectedTableSlug(first.slug);
    setChartAdjustOrigin("all-songs");
    setStep("adjust-chart");
  }

  function handleChooseTableForCandidate(slug: string) {
    if (!multiTableCandidate) return;
    const { item, candidates } = multiTableCandidate;
    const chosen = candidates.find((c) => c.slug === slug);
    if (!chosen) return;
    setChartPickCurrent({
      fumen: {
        sha256: item.sha256,
        md5: item.md5,
        title: item.title ?? "",
        artist: item.artist,
        level: chosen.level,
        symbol: chosen.symbol,
      },
      current: {
        clearType: item.user_score?.best_clear_type ?? null,
        rank: item.user_score?.rank ?? null,
        minBp: item.user_score?.best_min_bp ?? null,
        rate: item.user_score?.rate ?? null,
      },
      defaultClientType: item.user_score?.client_type ?? defaultClientType ?? "beatoraja",
    });
    setSelectedTableSlug(slug);
    setMultiTableCandidate(null);
    setChartAdjustOrigin("all-songs");
    setStep("adjust-chart");
  }

  function handleCalculatorSetGoal(draft: GoalDraft) {
    setPendingChart(draft);
    setClientType(draft.clientType || defaultClientType || "beatoraja");
    setStep("confirm");
  }

  function handleNoRatingAdjustContinue() {
    if (!chartPickCurrent) return;
    const baseline = noRatingBaselineQuery.data ?? { clear_type: null, min_bp: null, rank: null, rate: null };
    const clearChanged = noRatingAdjust.clearType !== (baseline.clear_type ?? 0);
    const bpChanged = (noRatingAdjust.minBp ?? null) !== (baseline.min_bp ?? null);
    const rateChanged = (noRatingAdjust.rate ?? null) !== (baseline.rate ?? null);
    const rankChanged = noRatingAdjust.rank !== (baseline.rank ?? rankGradeFromRate(baseline.rate));
    const draft: GoalDraft = {
      tableSlug: "",
      fumen: chartPickCurrent.fumen,
      clientType: chartPickCurrent.defaultClientType,
      clearType: clearChanged ? noRatingAdjust.clearType : null,
      minBp: bpChanged ? noRatingAdjust.minBp : null,
      rate: rateChanged ? noRatingAdjust.rate : null,
      rank: rankChanged ? noRatingAdjust.rank : null,
      projectedRating: null,
    };
    setPendingChart(draft);
    setClientType(chartPickCurrent.defaultClientType);
    setStep("confirm");
  }

  function handleSelectCourse(course: TargetCourse) {
    setPendingCourseTarget(course);
    setCourseAdjustClientType(defaultClientType ?? "beatoraja");
    setCourseAdjust({ clearType: 1, minBp: null, rate: null, rank: "F" });
    setStep("adjust-course");
  }

  function handleCourseAdjustContinue() {
    if (!pendingCourseTarget) return;
    const baseline = courseAdjustBaselineQuery.data ?? { clear_type: null, min_bp: null, rank: null, rate: null };
    const target = courseAdjustTarget(courseAdjust, baseline);
    const validation = validateGoalTarget(baseline, target);
    if (!validation.ok) return;
    setPendingCourse({
      ...target,
      course: pendingCourseTarget,
      clientType: courseAdjustClientType,
    });
    setClientType(courseAdjustClientType);
    setStep("confirm");
  }

  function handleSave() {
    setServerError(null);
    const payload = {
      goal_type: goalType!,
      client_type: clientType,
      table_slug: pendingChart?.tableSlug || null,
      fumen_sha256: pendingChart?.fumen.sha256 ?? null,
      fumen_md5: pendingChart?.fumen.md5 ?? null,
      course_id: pendingCourse?.course.course_id ?? null,
      target_clear_type: target.clearType,
      target_min_bp: target.minBp,
      target_rank: target.rank,
      target_rate: target.rate,
    };
    createGoal.mutate(payload, {
      onSuccess: () => handleClose(),
      onError: (err: unknown) => {
        setServerError(localizeGoalSaveError(err, t));
      },
    });
  }

  const wizardOpen = open && step !== "adjust-chart";
  /** Steps that own an internal scrolling list — these get a non-scrolling
   * outer wrapper so only the inner list scrolls (avoids nested/double scrollbars). */
  const isListStep = step === "table" || step === "chart-pick" || step === "course-pick";

  return (
    <>
      <Dialog open={wizardOpen} onOpenChange={(next) => !next && handleClose()}>
        <DialogContent className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden">
          <DialogHeader>
            <DialogTitle>{t("goals.setup.title")}</DialogTitle>
          </DialogHeader>

          <div
            className={cn(
              "flex-1 space-y-4 py-2",
              isListStep ? "flex min-h-0 flex-col overflow-hidden" : "overflow-y-auto",
            )}
          >
            {step === "type" && (
              <div className="space-y-3">
                <BackButton onClick={handleClose} label={t("common.actions.back")} />
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <button
                    type="button"
                    onClick={() => setStep("table")}
                    className="flex min-h-28 items-center justify-center gap-3 rounded-xl border border-border bg-card p-6 text-center transition-colors hover:border-primary hover:bg-primary/5"
                  >
                    <Music2 className="h-5 w-5 shrink-0 text-primary" />
                    <div className="text-lg font-semibold">{t("goals.setup.chartType")}</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setCourseScope("supported");
                      setSelectedCourseTableSlug(null);
                      setCourseSearch("");
                      setStep("course-pick");
                    }}
                    className="flex min-h-28 items-center justify-center gap-3 rounded-xl border border-border bg-card p-6 text-center transition-colors hover:border-primary hover:bg-primary/5"
                  >
                    <Trophy className="h-5 w-5 shrink-0 text-primary" />
                    <div className="text-lg font-semibold">{t("goals.setup.courseType")}</div>
                  </button>
                </div>
              </div>
            )}

            {step === "table" && (
              <div className="flex min-h-0 flex-1 flex-col gap-3">
                <BackButton onClick={() => setStep("type")} label={t("common.actions.back")} />
                <SegmentedOptions
                  value={chartScope}
                  options={[
                    ["rating", t("goals.setup.scopeRatingSupported")],
                    ["table", t("goals.setup.scopeByTable")],
                    ["all", t("goals.setup.scopeAllSongs")],
                  ]}
                  onChange={setChartScope}
                />

                {chartScope !== "all" ? (
                  rankingTablesQuery.isLoading || allTablesQuery.isLoading ? (
                    <Skeleton className="h-40 w-full" />
                  ) : (
                    <TableCategoryPicker
                      tables={chartScope === "rating"
                        ? (rankingTablesQuery.data ?? [])
                          .filter((table) => table.has_rating)
                          .map((table) => tableBySlug.get(table.slug))
                          .filter((table): table is DifficultyTable => table != null)
                        : allTables}
                      favorites={favoriteTables}
                      onSelect={(table) => table.slug && handleSelectTable(table.slug)}
                    />
                  )
                ) : (
                  <div className="flex min-h-0 flex-1 flex-col gap-2">
                    <GoalSearchBar
                      value={allSongsSearch}
                      onChange={(next) => {
                        setAllSongsSearch(next);
                        setAllSongsPage(1);
                      }}
                      field={allSongsSearchField}
                      onFieldChange={(next) => {
                        setAllSongsSearchField(next);
                        setAllSongsPage(1);
                      }}
                      fields={allSongSearchFields(t)}
                      placeholder={t("ranking.detail.searchPlaceholder")}
                    />
                    <AllSongsGoalTable
                      loading={allSongsQuery.isLoading}
                      items={allSongsQuery.data?.items ?? []}
                      tableSymbolById={tableSymbolById}
                      emptyMessage={t("common.states.noRecords")}
                      onSelect={handleSelectChartFromAllSongs}
                    />
                    {allSongsTotalPages > 1 && (
                      <Pagination
                        page={allSongsPage}
                        totalPages={allSongsTotalPages}
                        onPageChange={setAllSongsPage}
                        label={t("songs.pagination", { page: allSongsPage, totalPages: allSongsTotalPages })}
                        placeholder={t("pagination.placeholder")}
                      />
                    )}
                  </div>
                )}
              </div>
            )}

            {step === "chart-table-choice" && multiTableCandidate && (
              <div className="space-y-2">
                <BackButton onClick={() => { setMultiTableCandidate(null); setStep("table"); }} label={t("common.actions.back")} />
                <div className="text-body font-semibold">{multiTableCandidate.item.title}</div>
                <div className="text-caption text-muted-foreground">{t("goals.setup.chooseRatingTable")}</div>
                <div className="space-y-1">
                  {multiTableCandidate.candidates.map((c) => (
                    <button
                      key={c.slug}
                      type="button"
                      onClick={() => handleChooseTableForCandidate(c.slug)}
                      className="flex w-full items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-left transition-colors hover:border-primary hover:bg-primary/5"
                    >
                      <span className="shrink-0 rounded-md border border-primary/40 bg-primary/10 px-1.5 py-0.5 text-caption font-semibold text-primary">
                        {formatTableLevelWithSymbolForDisplay({ tableSymbol: c.symbol, level: c.level })}
                      </span>
                      <span className="text-body">{c.displayName}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {step === "chart-pick" && (
              <div className="flex min-h-0 flex-1 flex-col gap-2">
                <BackButton onClick={() => setStep("table")} label={t("common.actions.back")} />
                <ChartSearchTable
                  search={chartSearch}
                  onSearchChange={setChartSearch}
                  searchField={chartSearchField}
                  onSearchFieldChange={setChartSearchField}
                  loading={selectedChartTableHasRating ? chartRowsQuery.isLoading : tableSongsQuery.isLoading}
                  ratingRows={selectedChartTableHasRating ? filteredChartRows : []}
                  tableSongs={selectedChartTableHasRating ? [] : filteredTableSongs}
                  tableSymbol={selectedChartTable?.symbol}
                  levelCounts={chartLevelCounts}
                  selectedLevel={chartLevelFilter}
                  onLevelChange={setChartLevelFilter}
                  sortKey={chartSortKey}
                  sortDir={chartSortDir}
                  onSort={(key) => updateSort(key, chartSortKey, chartSortDir, setChartSortKey, setChartSortDir)}
                  emptyMessage={t("common.states.noRecords")}
                  onSelectRating={handleSelectChart}
                  onSelectTableSong={handleSelectTableSong}
                />
              </div>
            )}

            {step === "course-pick" && (
              <div className="flex min-h-0 flex-1 flex-col gap-3">
                <BackButton
                  onClick={() => {
                    if (selectedCourseTableSlug) {
                      setSelectedCourseTableSlug(null);
                      setCourseSearch("");
                    } else {
                      setStep("type");
                    }
                  }}
                  label={t("common.actions.back")}
                />
                {!selectedCourseTableSlug && (
                  <SegmentedOptions
                    value={courseScope}
                    options={[
                      ["supported", t("goals.setup.scopeSiteSupported")],
                      ["table", t("goals.setup.scopeByTable")],
                      ["all", t("goals.setup.scopeAllCourses")],
                    ]}
                    onChange={(scope) => {
                      setCourseScope(scope);
                      setSelectedCourseTableSlug(null);
                      setCourseSearch("");
                    }}
                  />
                )}
                {courseScope === "all" ? (
                  <CourseSearchList
                    search={courseSearch}
                    onSearchChange={setCourseSearch}
                    searchField={courseSearchField}
                    onSearchFieldChange={setCourseSearchField}
                    loading={targetCoursesQuery.isLoading}
                    courses={allScopeCourses}
                    sortKey={courseSortKey}
                    sortDir={courseSortDir}
                    onSort={(key) => updateSort(key, courseSortKey, courseSortDir, setCourseSortKey, setCourseSortDir)}
                    emptyMessage={t("common.states.noRecords")}
                    onSelect={handleSelectCourse}
                  />
                ) : selectedCourseTable ? (
                  <div className="flex min-h-0 flex-1 flex-col gap-2">
                    <div className="flex shrink-0 items-center gap-2">
                      {selectedCourseTable.symbol && (
                        <span className="rounded-md border border-border px-1.5 py-0.5 text-caption font-semibold">
                          {selectedCourseTable.symbol}
                        </span>
                      )}
                      <span className="min-w-0 truncate text-body font-semibold">{selectedCourseTable.name}</span>
                    </div>
                    <CourseSearchList
                      search={courseSearch}
                      onSearchChange={setCourseSearch}
                      searchField={courseSearchField}
                      onSearchFieldChange={setCourseSearchField}
                      loading={targetCoursesQuery.isLoading}
                      courses={tableScopedCourses}
                      sortKey={courseSortKey}
                      sortDir={courseSortDir}
                      onSort={(key) => updateSort(key, courseSortKey, courseSortDir, setCourseSortKey, setCourseSortDir)}
                      emptyMessage={t("goals.setup.noCoursesForTable")}
                      onSelect={handleSelectCourse}
                    />
                  </div>
                ) : targetCoursesQuery.isLoading || allTablesQuery.isLoading ? (
                  <Skeleton className="h-40 w-full" />
                ) : (
                  <CourseTableCategoryPicker
                    tables={courseTablesForScope}
                    courseCountBySlug={courseScope === "supported" ? supportedCourseCountBySlug : tableCourseCountBySlug}
                    favorites={favoriteTables}
                    showFavorites={courseScope === "table"}
                    groupBySource={courseScope === "table"}
                    onSelect={(table) => table.slug && setSelectedCourseTableSlug(table.slug)}
                  />
                )}
              </div>
            )}

            {step === "adjust-course" && pendingCourseTarget && (
              <CourseAdjustPanel
                course={pendingCourseTarget}
                baseline={courseAdjustBaselineQuery.data ?? null}
                baselineLoading={courseAdjustBaselineQuery.isLoading}
                value={courseAdjust}
                clientType={courseAdjustClientType}
                onChange={setCourseAdjust}
                onClientTypeChange={setCourseAdjustClientType}
                onBack={() => setStep("course-pick")}
                onContinue={handleCourseAdjustContinue}
              />
            )}

            {step === "adjust-chart-no-rating" && chartPickCurrent && (
              <div className="space-y-4">
                <BackButton onClick={() => setStep("table")} label={t("common.actions.back")} />
                <div className="text-body font-semibold">{chartPickCurrent.fumen.title}</div>
                <p className="text-caption text-muted-foreground">{t("goals.setup.noRatingTableNote")}</p>

                {noRatingBaselineQuery.isLoading ? (
                  <Skeleton className="h-16 w-full" />
                ) : (
                  <div className="space-y-1.5">
                    <div className="text-caption text-muted-foreground">{t("ranking.detail.calculator.current")}</div>
                    <div className="grid grid-cols-2 gap-3 rounded-lg border border-border bg-secondary/30 px-3 py-2 sm:grid-cols-4">
                      <div className="text-center text-caption font-semibold">
                        {noRatingBaselineQuery.data?.clear_type != null
                          ? CLEAR_TYPE_LABELS[noRatingBaselineQuery.data.clear_type] ?? String(noRatingBaselineQuery.data.clear_type)
                          : "—"}
                      </div>
                      <div className="text-center text-caption tabular-nums">{noRatingBaselineQuery.data?.min_bp ?? "—"}</div>
                      <div className="text-center text-caption tabular-nums">
                        {noRatingBaselineQuery.data?.rate != null ? formatRatePercent(noRatingBaselineQuery.data.rate) : "—"}
                      </div>
                      <div className="text-center text-caption font-semibold">{noRatingBaselineQuery.data?.rank ?? "—"}</div>
                    </div>
                  </div>
                )}

                <div className="space-y-1.5">
                  <div className="text-caption text-muted-foreground">{t("ranking.detail.calculator.adjusted")}</div>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Field label={t("common.fields.clear")}>
                      <select
                        value={noRatingAdjust.clearType}
                        onChange={(e) =>
                          setNoRatingAdjust(linkCourseAdjustFromClear(noRatingAdjust, Number(e.target.value), noRatingBaselineQuery.data ?? null))
                        }
                        className="h-9 w-full cursor-pointer rounded-md border border-border bg-card px-2 text-center text-caption font-semibold outline-none focus:border-primary"
                      >
                        {allowedClearTypes(noRatingBaselineQuery.data?.clear_type ?? null).map((ct) => (
                          <option key={ct} value={ct}>
                            {CLEAR_TYPE_LABELS[ct] ?? String(ct)}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="BP">
                      <Input
                        type="text"
                        inputMode="numeric"
                        value={noRatingAdjust.minBp ?? ""}
                        placeholder="-"
                        onChange={(e) => {
                          setNoRatingAdjust({
                            ...noRatingAdjust,
                            minBp: sanitizeBpInput(e.target.value, noRatingBaselineQuery.data?.min_bp ?? null),
                          });
                        }}
                        className="h-9 text-center tabular-nums"
                      />
                    </Field>
                    <Field label={t("common.fields.rate")}>
                      <Input
                        type="text"
                        inputMode="decimal"
                        value={noRatingAdjust.rate ?? ""}
                        placeholder="-"
                        onChange={(e) => {
                          setNoRatingAdjust(linkCourseAdjustFromRate(
                            noRatingAdjust,
                            sanitizeRateInput(e.target.value, noRatingBaselineQuery.data?.rate ?? null),
                          ));
                        }}
                        className="h-9 text-center tabular-nums"
                      />
                    </Field>
                    <Field label={t("common.fields.rank")}>
                      <select
                        value={noRatingAdjust.rank}
                        onChange={(e) => setNoRatingAdjust(linkCourseAdjustFromRank(noRatingAdjust, e.target.value))}
                        className="h-9 w-full cursor-pointer rounded-md border border-border bg-card px-2 text-center text-caption font-semibold outline-none focus:border-primary"
                      >
                        {allowedRanks(noRatingBaselineQuery.data?.rank ?? null).map((rank) => (
                          <option key={rank} value={rank}>{rank}</option>
                        ))}
                      </select>
                    </Field>
                  </div>
                </div>

                <div className="flex justify-end">
                  <Button onClick={handleNoRatingAdjustContinue}>{t("common.actions.next")}</Button>
                </div>
              </div>
            )}

            {step === "confirm" && goalType && (
              <ConfirmStep
                goalType={goalType}
                chart={pendingChart}
                course={pendingCourse}
                clientType={clientType}
                baseline={baselineQuery.data ?? null}
                baselineLoading={baselineQuery.isLoading}
                target={target}
                validation={validation}
                showBack
                onBack={() => {
                  if (initialDraft) {
                    handleClose();
                    return;
                  }
                  setStep(goalType === "chart" ? "adjust-chart" : "adjust-course");
                }}
              />
            )}
          </div>

          {step === "confirm" && goalType && (
            <DialogFooter className="flex-col items-stretch gap-2 sm:flex-row sm:items-center">
              {serverError && <p className="min-w-0 text-caption text-destructive sm:flex-1">{serverError}</p>}
              <div className="ml-auto flex justify-end gap-2">
                <Button
                  onClick={handleSave}
                  disabled={baselineQuery.isLoading || !validation?.ok || createGoal.isPending}
                  className="gap-2"
                >
                  {createGoal.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                  {t("goals.setup.save")}
                </Button>
              </div>
            </DialogFooter>
          )}
        </DialogContent>
      </Dialog>

      {chartPickCurrent && (
        <RatingCalculatorDialog
          open={open && step === "adjust-chart"}
          onClose={handleClose}
          onBack={() => setStep(chartAdjustOrigin === "all-songs" ? "table" : "chart-pick")}
          tableSlug={selectedTableSlug ?? ""}
          fumen={chartPickCurrent.fumen}
          ratingTableOptions={chartPickCurrent.ratingTableOptions}
          current={chartPickCurrent.current}
          clientType={chartPickCurrent.defaultClientType}
          titleOverride={t("goals.setup.title")}
          showBackButton
          onSetGoal={handleCalculatorSetGoal}
        />
      )}
    </>
  );
}

function BackButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <Button variant="ghost" size="sm" className="h-9 shrink-0 self-start justify-start gap-1 rounded-md text-muted-foreground" onClick={onClick}>
      <ChevronLeft className="h-4 w-4" />
      {label}
    </Button>
  );
}

function SegmentedOptions<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: [T, string][];
  onChange: (next: T) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map(([optionValue, label]) => (
        <button
          key={optionValue}
          type="button"
          onClick={() => onChange(optionValue)}
          className={cn(
            "rounded-md border px-3 py-1.5 text-caption font-semibold transition-colors",
            value === optionValue
              ? "border-primary bg-primary/10 text-primary"
              : "border-border bg-card text-muted-foreground hover:border-primary/50",
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function TableCategoryPicker({
  tables,
  favorites,
  onSelect,
}: {
  tables: DifficultyTable[];
  favorites: DifficultyTable[];
  onSelect: (table: DifficultyTable) => void;
}) {
  const { t } = useTranslation();
  const favoriteIds = new Set(favorites.map((table) => table.id));
  const countById = new Map(tables.map((table) => [table.id, table.song_count]));
  const visibleFavorites = favorites.filter((table) => tables.some((candidate) => candidate.id === table.id));
  const otherTables = tables.filter((table) => !favoriteIds.has(table.id));
  const defaultTables = otherTables.filter((table) => table.is_default);
  const userTables = otherTables.filter((table) => !table.is_default);

  return (
    <div className="min-h-0 flex-1 space-y-3 overflow-y-auto">
      <TablePickerSection title={t("tables.sidebar.favorites")} tables={visibleFavorites} countById={countById} onSelect={onSelect} />
      <TablePickerSection title={t("tables.sidebar.defaultTables")} tables={defaultTables} countById={countById} onSelect={onSelect} />
      <TablePickerSection title={t("tables.sidebar.userTables")} tables={userTables} countById={countById} onSelect={onSelect} />
      {tables.length === 0 && (
        <p className="py-6 text-center text-body text-muted-foreground">{t("common.states.noRecords")}</p>
      )}
    </div>
  );
}

function GoalSearchBar({
  value,
  onChange,
  field,
  onFieldChange,
  fields,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  field: GoalSearchField;
  onFieldChange: (value: GoalSearchField) => void;
  fields: { value: GoalSearchField; label: string }[];
  placeholder: string;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  function commitSearch() {
    onChange(draft);
  }

  return (
    <div className="flex shrink-0 flex-col gap-2 sm:flex-row sm:items-center">
      <Select value={field} onValueChange={(next) => onFieldChange(next as GoalSearchField)}>
        <SelectTrigger className="h-10 sm:w-44">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {fields.map((option) => (
            <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && commitSearch()}
        placeholder={placeholder}
        className="h-10 flex-1"
      />
      <Button type="button" onClick={commitSearch} className="h-10 gap-1.5">
        <Search className="h-4 w-4" />
        {t("songs.search.submit")}
      </Button>
    </div>
  );
}

function supportedSlugsForCourse(course: TargetCourse): string[] {
  return course.site_supported_table_slugs?.length
    ? course.site_supported_table_slugs
    : course.site_supported_table_slug
      ? [course.site_supported_table_slug]
      : [];
}

function localizeGoalSaveError(err: unknown, t: (key: string) => string): string {
  const message = err instanceof Error ? err.message : "";
  if (message === "An active goal already exists for this target") {
    return t("goals.setup.errors.duplicate_active_goal");
  }
  return message || t("goals.setup.saveError");
}

function compareCourseBadge(left: TargetCourse, right: TargetCourse): number {
  const leftHasBadge = !!left.dan_title;
  const rightHasBadge = !!right.dan_title;
  if (leftHasBadge !== rightHasBadge) return leftHasBadge ? -1 : 1;
  return compareBadgeText(left.dan_title ?? "", right.dan_title ?? "", left.dan_order, right.dan_order);
}

const COURSE_NAME_GRADE_ORDER: Array<[RegExp, number]> = [
  [/入門|intro|beginner/i, 0],
  [/初段|一段|1\s*(?:dan|段)|1_DAN/i, 1],
  [/二段|2\s*(?:dan|段)|2_DAN/i, 2],
  [/三段|3\s*(?:dan|段)|3_DAN/i, 3],
  [/四段|4\s*(?:dan|段)|4_DAN/i, 4],
  [/五段|5\s*(?:dan|段)|5_DAN/i, 5],
  [/六段|6\s*(?:dan|段)|6_DAN/i, 6],
  [/七段|7\s*(?:dan|段)|7_DAN/i, 7],
  [/八段|8\s*(?:dan|段)|8_DAN/i, 8],
  [/九段|9\s*(?:dan|段)|9_DAN/i, 9],
  [/十段|10\s*(?:dan|段)|10_DAN/i, 10],
  [/皆伝|kaiden/i, 11],
  [/gorilla/i, 12],
  [/over\s*joy|overjoy/i, 13],
];

function courseNameGradeIndex(name: string): number {
  for (const [pattern, index] of COURSE_NAME_GRADE_ORDER) {
    if (pattern.test(name)) return index;
  }
  return Number.POSITIVE_INFINITY;
}

function courseNameGradeMatch(name: string): { index: number; prefix: string } {
  let best: { index: number; prefix: string; at: number } | null = null;
  for (const [pattern, index] of COURSE_NAME_GRADE_ORDER) {
    const match = pattern.exec(name);
    if (!match || match.index == null) continue;
    if (best == null || match.index < best.at) {
      best = { index, prefix: name.slice(0, match.index).trim(), at: match.index };
    }
  }
  return best ?? { index: Number.POSITIVE_INFINITY, prefix: name.trim() };
}

function compareBadgeText(
  left: string,
  right: string,
  leftOrder: number | null | undefined,
  rightOrder: number | null | undefined,
): number {
  const leftPrefix = badgeSortPrefix(left);
  const rightPrefix = badgeSortPrefix(right);
  const prefixCmp = collator.compare(leftPrefix, rightPrefix);
  if (prefixCmp !== 0) return prefixCmp;

  const leftCourseBadgeRank = courseBadgeRank(left, leftOrder);
  const rightCourseBadgeRank = courseBadgeRank(right, rightOrder);
  if (leftCourseBadgeRank != null || rightCourseBadgeRank != null) {
    if (leftCourseBadgeRank == null) return 1;
    if (rightCourseBadgeRank == null) return -1;
    if (leftCourseBadgeRank !== rightCourseBadgeRank) return leftCourseBadgeRank - rightCourseBadgeRank;
    return collator.compare(left, right);
  }

  const leftMatch = /^(\D*?)(\d+)?\s*$/u.exec(left.trim());
  const rightMatch = /^(\D*?)(\d+)?\s*$/u.exec(right.trim());
  const leftNumber = leftMatch?.[2] ? Number(leftMatch[2]) : Number.POSITIVE_INFINITY;
  const rightNumber = rightMatch?.[2] ? Number(rightMatch[2]) : Number.POSITIVE_INFINITY;
  if (leftNumber !== rightNumber) return leftNumber - rightNumber;
  const normalizedLeftOrder = leftOrder ?? courseNameGradeIndex(left);
  const normalizedRightOrder = rightOrder ?? courseNameGradeIndex(right);
  if (normalizedLeftOrder !== normalizedRightOrder) return normalizedLeftOrder - normalizedRightOrder;
  return collator.compare(left, right);
}

function badgeSortPrefix(label: string): string {
  const normalized = label.trim();
  const numberMatch = /^(.*?)(?:0?(?:[1-9]|10))(?:\s*(?:dan|段))?$/iu.exec(normalized);
  if (numberMatch) return numberMatch[1].trim() || "#";
  if (normalized.includes("★★")) return normalized.replace(/★★.*/u, "").trim() || "★";
  if (/gorilla/i.test(normalized)) return normalized.replace(/gorilla.*/iu, "").trim() || "★";
  if (normalized.includes("(^^)")) return normalized.replace(/\(\^\^\).*/u, "").trim() || "★";
  const grade = courseNameGradeMatch(normalized);
  return grade.prefix || normalized;
}

function courseBadgeRank(label: string, order: number | null | undefined): number | null {
  const normalized = label.trim();
  if (!normalized) return null;
  const normalizedLower = normalized.toLowerCase();
  const normalizedOrder = typeof order === "number" ? order / 10 : null;

  if (normalized.includes("★★") || /皆伝|kaiden/i.test(normalized)) return 11;
  if (/gorilla/i.test(normalized)) return 12;
  if (normalized.includes("(^^)") || /over\s*joy|overjoy/i.test(normalized)) return 13;

  const numericBadge = /(?:^|[^\d])0?([1-9]|10)(?:[^\d]|$)/u.exec(normalized);
  if (numericBadge && !/^(?:sl|st|dp|sp)\d+$/i.test(normalized)) {
    return Number(numericBadge[1]);
  }

  const gradeIndex = courseNameGradeIndex(normalized);
  if (Number.isFinite(gradeIndex)) return gradeIndex;
  return normalizedOrder;
}

function compareCourseName(left: TargetCourse, right: TargetCourse): number {
  const leftGrade = courseNameGradeMatch(left.name);
  const rightGrade = courseNameGradeMatch(right.name);
  const prefixCmp = collator.compare(leftGrade.prefix, rightGrade.prefix);
  if (prefixCmp !== 0) return prefixCmp;
  if (leftGrade.index !== rightGrade.index) return leftGrade.index - rightGrade.index;
  return collator.compare(left.name, right.name);
}

function sortCourses(courses: TargetCourse[], key: CourseGoalSortKey, dir: SortDir): TargetCourse[] {
  return courses.slice().sort((a, b) => {
    if (a.is_active !== b.is_active) return a.is_active ? -1 : 1;
    let cmp = 0;
    if (key === "badge") {
      cmp = compareCourseBadge(a, b);
      if (cmp === 0) cmp = compareCourseName(a, b);
    } else if (key === "name") {
      cmp = compareCourseName(a, b);
    } else if (key === "clear") {
      cmp = (a.clear_type ?? -1) - (b.clear_type ?? -1);
    } else if (key === "rank") {
      cmp = compareRank(a.rank, b.rank);
    } else if (key === "active") {
      cmp = Number(a.is_active) - Number(b.is_active);
    }
    return dir === "asc" ? cmp : -cmp;
  });
}

function courseClearLabel(clearType: number | null | undefined): string {
  if (clearType == null) return "—";
  if (clearType === 4) return "CLEAR";
  return CLEAR_TYPE_LABELS[clearType] ?? String(clearType);
}

function allowedCourseClearTypes(baselineClearType: number | null): number[] {
  const normalizedBaseline = baselineClearType == null ? 0 : Math.min(9, Math.max(0, Math.trunc(baselineClearType)));
  return COURSE_GOAL_CLEAR_TYPES.filter((clearType) => clearType >= normalizedBaseline);
}

type RatingGoalRow = NonNullable<ReturnType<typeof useRankingContributionRows>["data"]>["entries"][number];

function AllSongsGoalTable({
  loading,
  items,
  tableSymbolById,
  emptyMessage,
  onSelect,
}: {
  loading: boolean;
  items: FumenListItem[];
  tableSymbolById: Map<string, string>;
  emptyMessage: string;
  onSelect: (item: FumenListItem) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="min-h-0 flex-1 overflow-auto overflow-x-hidden rounded-md border border-border">
      {loading ? (
        <Skeleton className="h-40 w-full" />
      ) : items.length === 0 ? (
        <p className="py-6 text-center text-body text-muted-foreground">{emptyMessage}</p>
      ) : (
        <table className="w-full table-fixed border-collapse text-left">
          <colgroup>
            <col className="w-[136px]" />
            <col />
            <col className="w-[88px]" />
            <col className="w-[58px]" />
          </colgroup>
          <thead className="sticky top-0 z-10 bg-card text-caption text-muted-foreground">
            <tr className="border-b border-border">
              <th className="px-2 py-2 font-medium">{t("common.fields.level")}</th>
              <th className="px-2 py-2 font-medium">{t("common.fields.titleArtist")}</th>
              <th className="px-2 py-2 font-medium">{t("common.fields.clear")}</th>
              <th className="px-2 py-2 font-medium">{t("common.fields.rank")}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const score = item.user_score;
              const clearType = displayClearType(score?.best_clear_type ?? null, { rate: score?.rate }) ?? score?.best_clear_type ?? null;
              const levels = (item.table_entries ?? []).map((entry) => ({
                symbol: tableSymbolById.get(entry.table_id) ?? "",
                slug: entry.table_id,
                level: entry.level,
              }));
              return (
                <tr
                  key={`${item.sha256 ?? ""}-${item.md5 ?? ""}`}
                  onClick={() => onSelect(item)}
                  className={cn("cursor-pointer border-b border-border/30", clearType != null ? CLEAR_ROW_CLASS[clearType] : "hover:bg-secondary/50")}
                >
                  <td className="px-2 py-2">
                    <div className="min-w-0 truncate">
                      <TableLevelBadges levels={levels} maxVisible={2} />
                    </div>
                  </td>
                  <td className="min-w-0 px-2 py-2">
                    <div className="min-w-0">
                      <div className="truncate text-label font-medium">{item.title ?? t("fumen.detail.untitled")}</div>
                      {item.artist && <div className="truncate text-caption row-muted">{item.artist}</div>}
                    </div>
                  </td>
                  <td className="px-2 py-2 text-label whitespace-nowrap">
                    {score ? (CLEAR_TYPE_LABELS[score.best_clear_type ?? 0] ?? "—") : "—"}
                  </td>
                  <td className="px-2 py-2 text-label font-semibold">{score?.rank ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

function updateSort<T extends string>(
  key: T,
  currentKey: T,
  currentDir: SortDir,
  setKey: (value: T) => void,
  setDir: (value: SortDir) => void,
) {
  if (key === currentKey) {
    setDir(currentDir === "asc" ? "desc" : "asc");
    return;
  }
  setKey(key);
  setDir("asc");
}

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return <span className="ml-0.5 text-muted-foreground/35">⇅</span>;
  return <span className="ml-0.5">{dir === "asc" ? "↑" : "↓"}</span>;
}

function SortTh<T extends string>({
  col,
  label,
  sortKey,
  sortDir,
  onSort,
  className,
}: {
  col: T;
  label: string;
  sortKey: T;
  sortDir: SortDir;
  onSort: (key: T) => void;
  className?: string;
}) {
  return (
    <th
      className={cn("cursor-pointer select-none px-2 py-2 text-left font-medium whitespace-nowrap hover:text-foreground", className)}
      onClick={() => onSort(col)}
    >
      {label}<SortIcon active={sortKey === col} dir={sortDir} />
    </th>
  );
}

function chartSearchFields(t: ReturnType<typeof useTranslation>["t"]) {
  return [
    { value: "title_artist" as const, label: t("common.fields.titleArtist") },
    { value: "title" as const, label: t("common.fields.title") },
    { value: "artist" as const, label: t("common.fields.artist") },
    { value: "clear" as const, label: t("common.fields.clear") },
    { value: "bp" as const, label: t("common.fields.bp") },
    { value: "rate" as const, label: t("common.fields.rate") },
    { value: "rank" as const, label: t("common.fields.rank") },
  ];
}

function allSongSearchFields(t: ReturnType<typeof useTranslation>["t"]) {
  return [
    { value: "title_artist" as const, label: t("common.fields.titleArtist") },
    { value: "title" as const, label: t("common.fields.title") },
    { value: "artist" as const, label: t("common.fields.artist") },
    { value: "level" as const, label: t("common.fields.level") },
  ];
}

function courseSearchFields(t: ReturnType<typeof useTranslation>["t"]) {
  return [
    { value: "name" as const, label: t("common.fields.name") },
    { value: "badge" as const, label: t("goals.setup.badge") },
    { value: "clear" as const, label: t("common.fields.clear") },
    { value: "rank" as const, label: t("common.fields.rank") },
    { value: "active" as const, label: t("goals.setup.active") },
  ];
}

function filterChartGoalRows(rows: RatingGoalRow[], query: string, field: GoalSearchField): RatingGoalRow[] {
  const q = query.trim();
  if (!q) return rows;
  return rows.filter((row) => {
    switch (field) {
      case "title_artist":
        return anyTextMatchesLooseQuery([row.title, row.artist], q);
      case "title":
        return anyTextMatchesLooseQuery([row.title], q);
      case "artist":
        return anyTextMatchesLooseQuery([row.artist], q);
      case "clear":
        return anyTextMatchesLooseQuery([CLEAR_TYPE_LABELS[row.clear_type] ?? String(row.clear_type)], q);
      case "bp":
        return anyTextMatchesLooseQuery([row.min_bp], q);
      case "rate":
        return anyTextMatchesLooseQuery([row.rate != null ? formatRatePercent(row.rate) : null], q);
      case "rank":
        return anyTextMatchesLooseQuery([row.rank_grade], q);
      default:
        return true;
    }
  });
}

function filterTableFumensForGoal(rows: TableFumen[], query: string, field: GoalSearchField): TableFumen[] {
  const q = query.trim();
  if (!q) return rows;
  return rows.filter((row) => {
    const score = row.user_score;
    switch (field) {
      case "title_artist":
        return anyTextMatchesLooseQuery([row.title, row.artist], q);
      case "title":
        return anyTextMatchesLooseQuery([row.title], q);
      case "artist":
        return anyTextMatchesLooseQuery([row.artist], q);
      case "clear":
        return anyTextMatchesLooseQuery([score?.best_clear_type != null ? CLEAR_TYPE_LABELS[score.best_clear_type] : null], q);
      case "bp":
        return anyTextMatchesLooseQuery([score?.best_min_bp], q);
      case "rate":
        return anyTextMatchesLooseQuery([score?.rate != null ? formatRatePercent(score.rate) : null], q);
      case "rank":
        return anyTextMatchesLooseQuery([score?.rank], q);
      default:
        return true;
    }
  });
}

function compareNullableNumber(left: number | null | undefined, right: number | null | undefined): number {
  const l = left ?? Number.POSITIVE_INFINITY;
  const r = right ?? Number.POSITIVE_INFINITY;
  return l - r;
}

function compareRank(left: string | null | undefined, right: string | null | undefined): number {
  return rankIndex(left) - rankIndex(right);
}

function sortChartGoalRows(rows: RatingGoalRow[], key: ChartGoalSortKey, dir: SortDir): RatingGoalRow[] {
  return rows.slice().sort((a, b) => {
    let cmp = 0;
    if (key === "title") cmp = collator.compare(a.title ?? "", b.title ?? "");
    else if (key === "clear") cmp = (a.clear_type ?? -1) - (b.clear_type ?? -1);
    else if (key === "bp") cmp = compareNullableNumber(a.min_bp, b.min_bp);
    else if (key === "rate") cmp = (a.rate ?? -1) - (b.rate ?? -1);
    else if (key === "rank") cmp = compareRank(a.rank_grade, b.rank_grade);
    return dir === "asc" ? cmp : -cmp;
  });
}

function sortTableFumensForGoal(rows: TableFumen[], key: ChartGoalSortKey, dir: SortDir): TableFumen[] {
  return rows.slice().sort((a, b) => {
    let cmp = 0;
    const as = a.user_score;
    const bs = b.user_score;
    if (key === "title") cmp = collator.compare(a.title ?? "", b.title ?? "");
    else if (key === "clear") cmp = (as?.best_clear_type ?? -1) - (bs?.best_clear_type ?? -1);
    else if (key === "bp") cmp = compareNullableNumber(as?.best_min_bp, bs?.best_min_bp);
    else if (key === "rate") cmp = (as?.rate ?? -1) - (bs?.rate ?? -1);
    else if (key === "rank") cmp = compareRank(as?.rank, bs?.rank);
    return dir === "asc" ? cmp : -cmp;
  });
}

function courseDedupeKey(course: TargetCourse): string {
  if (course.dan_title) return `dan:${course.dan_title}`;
  return `name:${course.table_slug ?? ""}:${course.name}`;
}

function preferCourseRepresentative(left: TargetCourse, right: TargetCourse): TargetCourse {
  if (left.is_active !== right.is_active) return left.is_active ? left : right;
  if ((left.dan_order ?? Number.POSITIVE_INFINITY) !== (right.dan_order ?? Number.POSITIVE_INFINITY)) {
    return (left.dan_order ?? Number.POSITIVE_INFINITY) < (right.dan_order ?? Number.POSITIVE_INFINITY) ? left : right;
  }
  return collator.compare(left.name, right.name) <= 0 ? left : right;
}

function dedupeGoalCourses(courses: TargetCourse[]): TargetCourse[] {
  const map = new Map<string, TargetCourse>();
  for (const course of courses) {
    const key = courseDedupeKey(course);
    const existing = map.get(key);
    map.set(key, existing ? preferCourseRepresentative(existing, course) : course);
  }
  return Array.from(map.values());
}

function filterCoursesForGoal(courses: TargetCourse[], query: string, field: GoalSearchField): TargetCourse[] {
  const q = query.trim();
  if (!q) return courses;
  return courses.filter((course) => {
    switch (field) {
      case "name":
        return anyTextMatchesLooseQuery([course.name], q);
      case "badge":
        return anyTextMatchesLooseQuery([course.dan_title], q);
      case "clear":
        return anyTextMatchesLooseQuery([courseClearLabel(course.clear_type)], q);
      case "rank":
        return anyTextMatchesLooseQuery([course.rank], q);
      case "active":
        return anyTextMatchesLooseQuery([course.is_active ? "active 활성화 有効" : "inactive 비활성 無効"], q);
      default:
        return anyTextMatchesLooseQuery([course.name, course.dan_title], q);
    }
  });
}

function ChartSearchTable({
  search,
  onSearchChange,
  searchField,
  onSearchFieldChange,
  loading,
  ratingRows,
  tableSongs,
  tableSymbol,
  levelCounts,
  selectedLevel,
  onLevelChange,
  sortKey,
  sortDir,
  onSort,
  emptyMessage,
  onSelectRating,
  onSelectTableSong,
}: {
  search: string;
  onSearchChange: (value: string) => void;
  searchField: GoalSearchField;
  onSearchFieldChange: (value: GoalSearchField) => void;
  loading: boolean;
  ratingRows: RatingGoalRow[];
  tableSongs: TableFumen[];
  tableSymbol?: string | null;
  levelCounts: [string, number][];
  selectedLevel: string | null;
  onLevelChange: (value: string | null) => void;
  sortKey: ChartGoalSortKey;
  sortDir: SortDir;
  onSort: (key: ChartGoalSortKey) => void;
  emptyMessage: string;
  onSelectRating: (row: RatingGoalRow) => void;
  onSelectTableSong: (row: TableFumen) => void;
}) {
  const { t } = useTranslation();
  const hasRatingRows = ratingRows.length > 0;
  const hasTableSongs = tableSongs.length > 0;
  const effectiveSelectedLevel = selectedLevel ?? levelCounts[0]?.[0] ?? null;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <GoalSearchBar
        value={search}
        onChange={onSearchChange}
        field={searchField}
        onFieldChange={onSearchFieldChange}
        fields={chartSearchFields(t)}
        placeholder={t("ranking.detail.searchPlaceholder")}
      />
      <div className="flex min-h-0 flex-1 overflow-hidden rounded-md border border-border">
        <div className="w-24 shrink-0 overflow-y-auto border-r border-border">
          {levelCounts.map(([level, count]) => (
            <button
              key={level}
              type="button"
              onClick={() => onLevelChange(level)}
              className={cn(
                "flex min-h-9 w-full items-center justify-between px-2 text-left text-label transition-colors",
                effectiveSelectedLevel === level ? "bg-primary/10 font-medium text-primary" : "text-muted-foreground hover:bg-secondary",
              )}
            >
              <span className="truncate">{formatTableLevelWithSymbolForDisplay({ tableSymbol, level })}</span>
              <span className="text-caption opacity-70">{count}</span>
            </button>
          ))}
        </div>
        <div className="min-w-0 flex-1 overflow-auto">
          {loading ? (
            <Skeleton className="h-40 w-full" />
          ) : !hasRatingRows && !hasTableSongs ? (
            <p className="py-6 text-center text-body text-muted-foreground">{emptyMessage}</p>
          ) : (
            <table className="w-full table-fixed border-collapse text-left">
              <colgroup>
                <col />
                <col className="w-[88px]" />
                <col className="w-[48px]" />
                <col className="w-[68px]" />
                <col className="w-[58px]" />
              </colgroup>
              <thead className="sticky top-0 z-10 bg-card text-caption text-muted-foreground">
                <tr className="border-b border-border">
                  <SortTh col="title" label={t("common.fields.titleArtist")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <SortTh col="clear" label={t("common.fields.clear")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <SortTh col="bp" label={t("common.fields.bp")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <SortTh col="rate" label={t("common.fields.rate")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <SortTh col="rank" label={t("common.fields.rank")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                </tr>
              </thead>
              <tbody>
                {ratingRows.map((row) => {
                  const clearType = displayClearType(row.clear_type, { rate: row.rate }) ?? row.clear_type;
                  return (
                    <tr
                      key={`${row.sha256 ?? ""}-${row.md5 ?? ""}`}
                      onClick={() => onSelectRating(row)}
                      className={cn("cursor-pointer border-b border-border/30", CLEAR_ROW_CLASS[clearType] ?? "hover:bg-secondary/50")}
                    >
                      <td className="min-w-0 px-2 py-2">
                        <div className="min-w-0">
                          <div className="truncate text-label font-medium">{row.title}</div>
                          {row.artist && <div className="truncate text-caption row-muted">{row.artist}</div>}
                        </div>
                      </td>
                      <td className="px-2 py-2 text-label whitespace-nowrap">{CLEAR_TYPE_LABELS[row.clear_type] ?? "—"}</td>
                      <td className="px-2 py-2 text-label tabular-nums">{row.min_bp ?? "—"}</td>
                      <td className="px-2 py-2 text-label tabular-nums">{row.rate != null ? formatRatePercent(row.rate) : "—"}</td>
                      <td className="px-2 py-2 text-label font-semibold">{row.rank_grade ?? "—"}</td>
                    </tr>
                  );
                })}
                {tableSongs.map((row) => {
                  const score = row.user_score;
                  const clearType = displayClearType(score?.best_clear_type ?? null, { exscore: score?.best_exscore, rate: score?.rate });
                  return (
                    <tr
                      key={row.fumen_id}
                      onClick={() => onSelectTableSong(row)}
                      className={cn("cursor-pointer border-b border-border/30", clearType != null ? CLEAR_ROW_CLASS[clearType] : "hover:bg-secondary/50")}
                    >
                      <td className="min-w-0 px-2 py-2">
                        <div className="min-w-0">
                          <div className="truncate text-label font-medium">{row.title ?? t("fumen.detail.untitled")}</div>
                          {row.artist && <div className="truncate text-caption row-muted">{row.artist}</div>}
                        </div>
                      </td>
                      <td className="px-2 py-2 text-label whitespace-nowrap">{score ? (CLEAR_TYPE_LABELS[score.best_clear_type ?? 0] ?? "—") : "—"}</td>
                      <td className="px-2 py-2 text-label tabular-nums">{score?.best_min_bp ?? "—"}</td>
                      <td className="px-2 py-2 text-label tabular-nums">{score?.rate != null ? formatRatePercent(score.rate) : "—"}</td>
                      <td className="px-2 py-2 text-label font-semibold">{score?.rank ?? "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

function TablePickerSection({
  title,
  tables,
  countById,
  onSelect,
}: {
  title: string;
  tables: DifficultyTable[];
  countById: Map<string, number | null | undefined>;
  onSelect: (table: DifficultyTable) => void;
}) {
  if (tables.length === 0) return null;
  return (
    <div className="space-y-1">
      <div className="text-caption font-semibold text-muted-foreground">{title}</div>
      <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
        {tables.map((table) => (
          <button
            key={table.id}
            type="button"
            onClick={() => onSelect(table)}
            className="flex min-h-10 items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-left transition-colors hover:border-primary hover:bg-primary/5"
          >
            {table.symbol && (
              <span className="shrink-0 rounded-md border border-border px-1.5 py-0.5 text-caption font-semibold">
                {table.symbol}
              </span>
            )}
            <span className="min-w-0 flex-1 truncate text-label font-medium">{table.name}</span>
            <span className="shrink-0 text-caption text-muted-foreground">{table.song_count ?? countById.get(table.id) ?? 0}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

/** Difficulty-table picker for the course-goal flow. Unlike the chart flow's
 * TableCategoryPicker, this never shows a "Favorites" section (favoriting a
 * table is unrelated to which tables have courses), skips source-type
 * grouping entirely for the curated "site supported" scope, and shows the
 * actual course count for the active scope instead of the table's song count. */
function CourseTableCategoryPicker({
  tables,
  courseCountBySlug,
  favorites,
  showFavorites,
  groupBySource,
  onSelect,
}: {
  tables: DifficultyTable[];
  courseCountBySlug: Map<string, { active: number; total: number }>;
  favorites: DifficultyTable[];
  showFavorites: boolean;
  groupBySource: boolean;
  onSelect: (table: DifficultyTable) => void;
}) {
  const { t } = useTranslation();
  const favoriteIds = new Set(favorites.map((table) => table.id));
  const visibleFavorites = showFavorites ? favorites.filter((table) => tables.some((candidate) => candidate.id === table.id)) : [];
  const otherTables = tables.filter((table) => !favoriteIds.has(table.id));
  const defaultTables = groupBySource ? otherTables.filter((table) => table.is_default) : [];
  const userTables = groupBySource ? otherTables.filter((table) => !table.is_default) : [];

  return (
    <div className="min-h-0 flex-1 space-y-3 overflow-y-auto">
      {groupBySource ? (
        <>
          <CourseTablePickerSection
            title={t("tables.sidebar.favorites")}
            tables={visibleFavorites}
            courseCountBySlug={courseCountBySlug}
            onSelect={onSelect}
          />
          <CourseTablePickerSection
            title={t("tables.sidebar.defaultTables")}
            tables={defaultTables}
            courseCountBySlug={courseCountBySlug}
            onSelect={onSelect}
          />
          <CourseTablePickerSection
            title={t("tables.sidebar.userTables")}
            tables={userTables}
            courseCountBySlug={courseCountBySlug}
            onSelect={onSelect}
          />
        </>
      ) : (
        <CourseTablePickerSection title={null} tables={tables} courseCountBySlug={courseCountBySlug} onSelect={onSelect} />
      )}
      {tables.length === 0 && (
        <p className="py-6 text-center text-body text-muted-foreground">{t("common.states.noRecords")}</p>
      )}
    </div>
  );
}

function CourseTablePickerSection({
  title,
  tables,
  courseCountBySlug,
  onSelect,
}: {
  title: string | null;
  tables: DifficultyTable[];
  courseCountBySlug: Map<string, { active: number; total: number }>;
  onSelect: (table: DifficultyTable) => void;
}) {
  if (tables.length === 0) return null;
  return (
    <div className="space-y-1">
      {title && <div className="text-caption font-semibold text-muted-foreground">{title}</div>}
      <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
        {tables.map((table) => (
          <button
            key={table.id}
            type="button"
            onClick={() => onSelect(table)}
            className="flex min-h-10 items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-left transition-colors hover:border-primary hover:bg-primary/5"
          >
            {table.symbol && (
              <span className="shrink-0 rounded-md border border-border px-1.5 py-0.5 text-caption font-semibold">
                {table.symbol}
              </span>
            )}
            <span className="min-w-0 flex-1 truncate text-label font-medium">{table.name}</span>
            <span className="shrink-0 text-caption text-muted-foreground">
              {formatCourseCount(courseCountBySlug.get(table.slug ?? ""))}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function formatCourseCount(count: { active: number; total: number } | undefined): string {
  return `${count?.active ?? 0}/${count?.total ?? 0}`;
}

function CourseSearchList({
  search,
  onSearchChange,
  searchField,
  onSearchFieldChange,
  loading,
  courses,
  sortKey,
  sortDir,
  onSort,
  emptyMessage,
  onSelect,
}: {
  search: string;
  onSearchChange: (value: string) => void;
  searchField: GoalSearchField;
  onSearchFieldChange: (value: GoalSearchField) => void;
  loading: boolean;
  courses: TargetCourse[];
  sortKey: CourseGoalSortKey;
  sortDir: SortDir;
  onSort: (key: CourseGoalSortKey) => void;
  emptyMessage: string;
  onSelect: (course: TargetCourse) => void;
}) {
  const { t } = useTranslation();
  const activeCourses = courses.filter((course) => course.is_active);
  const inactiveCourses = courses.filter((course) => !course.is_active);
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <GoalSearchBar
        value={search}
        onChange={onSearchChange}
        field={searchField}
        onFieldChange={onSearchFieldChange}
        fields={courseSearchFields(t)}
        placeholder={t("ranking.detail.searchPlaceholder")}
      />
      <div className="min-h-0 flex-1 overflow-auto overflow-x-hidden rounded-md border border-border">
        {loading ? (
          <Skeleton className="h-40 w-full" />
        ) : courses.length === 0 ? (
          <p className="py-6 text-center text-body text-muted-foreground">{emptyMessage}</p>
        ) : (
          <TooltipProvider delayDuration={200}>
            <table className="w-full table-fixed border-collapse text-left">
              <colgroup>
                <col className="w-[86px]" />
                <col />
                <col className="w-[82px]" />
                <col className="w-[64px]" />
                <col className="w-[64px]" />
              </colgroup>
              <thead className="sticky top-0 z-10 bg-card text-caption text-muted-foreground">
                <tr className="border-b border-border">
                  <SortTh col="badge" label={t("goals.setup.badge")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <SortTh col="name" label={t("common.fields.name")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <SortTh col="clear" label={t("common.fields.clear")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <SortTh col="rank" label={t("common.fields.rank")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <SortTh col="active" label={t("goals.setup.active")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} className="text-center" />
                </tr>
              </thead>
              <tbody>
                <CourseRowsSection title={t("goals.setup.activeCourses")} courses={activeCourses} onSelect={onSelect} />
                <CourseRowsSection title={t("goals.setup.inactiveCourses")} courses={inactiveCourses} onSelect={onSelect} />
              </tbody>
            </table>
          </TooltipProvider>
        )}
      </div>
    </div>
  );
}

function CourseRowsSection({
  title,
  courses,
  onSelect,
}: {
  title: string;
  courses: TargetCourse[];
  onSelect: (course: TargetCourse) => void;
}) {
  if (courses.length === 0) return null;
  return (
    <>
      <tr className="bg-secondary/40">
        <td colSpan={5} className="px-2 py-1.5 text-caption font-semibold text-muted-foreground">
          {title}
        </td>
      </tr>
      {courses.map((course) => (
        <CourseRow key={course.course_id} course={course} onSelect={onSelect} />
      ))}
    </>
  );
}

function CourseRow({ course, onSelect }: { course: TargetCourse; onSelect: (course: TargetCourse) => void }) {
  const { t } = useTranslation();
  const clearType = displayClearType(course.clear_type, { rate: course.rate }) ?? course.clear_type;
  return (
    <tr
      onClick={() => onSelect(course)}
      className={cn("cursor-pointer border-b border-border/30", clearType != null ? CLEAR_ROW_CLASS[clearType] : "hover:bg-secondary/50")}
    >
      <td className="px-2 py-2">
        {course.dan_title ? (
          <span className="inline-flex rounded-md border border-accent/40 bg-accent/10 px-1.5 py-0.5 text-caption font-semibold text-accent">
            {course.dan_title}
          </span>
        ) : (
          <span className="text-label row-muted">—</span>
        )}
      </td>
      <td className="px-2 py-2">
        <div className="truncate text-label font-medium">{course.name}</div>
      </td>
      <td className="px-2 py-2 text-label">{courseClearLabel(course.clear_type)}</td>
      <td className="px-2 py-2 text-label font-semibold">{course.rank ?? "—"}</td>
      <td className="px-2 py-2 text-center">
        <Tooltip>
          <TooltipTrigger asChild>
            <span className={cn("inline-flex justify-center", course.is_active ? "text-primary" : "text-destructive")}>
              {course.is_active ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}
            </span>
          </TooltipTrigger>
          <TooltipContent>
            {course.is_active ? t("goals.setup.courseActiveTooltip") : t("goals.setup.courseInactiveTooltip")}
          </TooltipContent>
        </Tooltip>
      </td>
    </tr>
  );
}

function clampClearType(value: number, baselineClearType: number | null): number {
  const normalizedBaseline = baselineClearType == null ? 0 : Math.min(9, Math.max(0, Math.trunc(baselineClearType)));
  return value < normalizedBaseline ? normalizedBaseline : value;
}

function rankIndex(rank: string | null | undefined): number {
  return rank ? RATING_RANKS.indexOf(rank) : -1;
}

function allowedClearTypes(baselineClearType: number | null): number[] {
  const normalizedBaseline = baselineClearType == null ? 0 : Math.min(9, Math.max(0, Math.trunc(baselineClearType)));
  return RATING_CLEAR_TYPES.filter((clearType) => clearType >= normalizedBaseline);
}

function allowedRanks(baselineRank: string | null): string[] {
  const baselineIndex = rankIndex(baselineRank);
  return RATING_RANKS.filter((rank) => rankIndex(rank) >= baselineIndex);
}

function linkCourseAdjustFromClear(value: CourseAdjust, clearType: number, baseline: GoalBaseline | null): CourseAdjust {
  const nextClear = clampClearType(clearType, baseline?.clear_type ?? null);
  if (nextClear === 9) {
    return { ...value, clearType: 9, rate: 100, rank: "MAX" };
  }
  return { ...value, clearType: nextClear };
}

function linkCourseAdjustFromRate(value: CourseAdjust, rate: number | null): CourseAdjust {
  if (rate === 100) {
    return { ...value, clearType: 9, rate: 100, rank: "MAX" };
  }
  return { ...value, rate, rank: rankGradeFromRate(rate) };
}

function linkCourseAdjustFromRank(value: CourseAdjust, rank: string): CourseAdjust {
  const rate = minRateForRank(rank);
  if (rank === "MAX") {
    return { ...value, clearType: 9, rate, rank };
  }
  return { ...value, rate, rank };
}

function courseAdjustTarget(value: CourseAdjust, baseline: GoalBaseline | null): CourseAdjustDiff {
  const clearChanged = value.clearType !== (baseline?.clear_type ?? 0);
  const bpChanged = (value.minBp ?? null) !== (baseline?.min_bp ?? null);
  const rateChanged = (value.rate ?? null) !== (baseline?.rate ?? null);
  const rankChanged = value.rank !== (baseline?.rank ?? rankGradeFromRate(baseline?.rate ?? null));
  return {
    clearType: clearChanged ? value.clearType : null,
    minBp: bpChanged ? value.minBp : null,
    rate: rateChanged ? value.rate : null,
    rank: rankChanged ? value.rank : null,
  };
}

const COURSE_GOAL_GRID_TEMPLATE = "grid-cols-[minmax(112px,1fr)_minmax(88px,0.8fr)_minmax(104px,0.9fr)_minmax(72px,0.7fr)]";

function CourseGoalCell({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex min-w-0 items-center justify-center px-2 py-3 text-label", className)}>
      {children}
    </div>
  );
}

function CourseGoalColumnHeader({ t }: { t: (key: string) => string }) {
  return (
    <div className={cn("grid border-b border-border text-label font-medium text-muted-foreground", COURSE_GOAL_GRID_TEMPLATE)}>
      <div className="px-2 py-2 text-center">{t("common.fields.clear")}</div>
      <div className="px-2 py-2 text-center">BP</div>
      <div className="px-2 py-2 text-center">{t("common.fields.rate")}</div>
      <div className="px-2 py-2 text-center">{t("common.fields.rank")}</div>
    </div>
  );
}

function CourseAdjustPanel({
  course,
  baseline,
  baselineLoading,
  value,
  clientType,
  onChange,
  onClientTypeChange,
  onBack,
  onContinue,
}: {
  course: TargetCourse;
  baseline: GoalBaseline | null;
  baselineLoading: boolean;
  value: CourseAdjust;
  clientType: string;
  onChange: (next: CourseAdjust) => void;
  onClientTypeChange: (next: string) => void;
  onBack: () => void;
  onContinue: () => void;
}) {
  const { t } = useTranslation();
  const currentClear = baseline?.clear_type ?? 0;
  const adjustedClear = value.clearType;
  const target = courseAdjustTarget(value, baseline);
  const hasAnyChange = Object.values(target).some((metric) => metric != null);
  const validation = baselineLoading ? null : validateGoalTarget(
    baseline ?? { clear_type: null, min_bp: null, rank: null, rate: null },
    target,
  );

  return (
    <div className="space-y-4">
      <BackButton onClick={onBack} label={t("common.actions.back")} />
      <div className="flex items-center gap-2">
        {course.dan_title && (
          <span className="shrink-0 rounded-md border border-accent/40 bg-accent/10 px-2 py-0.5 text-caption font-semibold text-accent">
            {course.dan_title}
          </span>
        )}
        <span className="min-w-0 truncate text-body font-semibold">{course.name}</span>
      </div>

      {baselineLoading ? (
        <Skeleton className="h-16 w-full" />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card/60">
          <div className="flex min-h-10 items-center border-b border-border/50 bg-secondary/40 px-4 py-2">
            <span className="text-caption font-semibold text-muted-foreground">
              {t("ranking.detail.calculator.current")}
            </span>
          </div>
          <CourseGoalColumnHeader t={t} />
          <div className={cn("grid items-stretch", COURSE_GOAL_GRID_TEMPLATE, CLEAR_ROW_STATIC_CLASS[currentClear] ?? "")}>
            <CourseGoalCell className="font-semibold">
              {baseline?.clear_type != null ? courseClearLabel(baseline.clear_type) : "—"}
            </CourseGoalCell>
            <CourseGoalCell className="tabular-nums">{baseline?.min_bp ?? "—"}</CourseGoalCell>
            <CourseGoalCell className="tabular-nums">
              {baseline?.rate != null ? formatRatePercent(baseline.rate) : "—"}
            </CourseGoalCell>
            <CourseGoalCell className="font-semibold">{baseline?.rank ?? "—"}</CourseGoalCell>
          </div>
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-border bg-card/60">
        <div className="flex min-h-10 items-center border-b border-border/50 bg-secondary/40 px-4 py-2">
          <span className="text-caption font-semibold text-primary">
            {t("ranking.detail.calculator.adjusted")}
          </span>
          <div className="ml-auto flex items-center gap-1">
            {CLIENT_TYPES.map((ct) => (
              <button
                key={ct}
                type="button"
                onClick={() => onClientTypeChange(ct)}
                className={cn(
                  "rounded-md border px-2 py-1 text-caption font-semibold transition-colors",
                  clientType === ct
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-card text-muted-foreground hover:border-primary/50",
                )}
              >
                {CLIENT_LABELS[ct]}
              </button>
            ))}
          </div>
        </div>
        <CourseGoalColumnHeader t={t} />
        <div className={cn("grid items-stretch", COURSE_GOAL_GRID_TEMPLATE, CLEAR_ROW_STATIC_CLASS[adjustedClear] ?? "")}>
          <CourseGoalCell>
            <select
              value={value.clearType}
              onChange={(e) => onChange(linkCourseAdjustFromClear(value, Number(e.target.value), baseline))}
              className="h-9 w-full cursor-pointer rounded-md border border-border bg-card px-2 text-center text-caption font-semibold outline-none focus:border-primary"
            >
              {allowedCourseClearTypes(baseline?.clear_type ?? null).map((ct) => (
                <option key={ct} value={ct}>
                  {courseClearLabel(ct)}
                </option>
              ))}
            </select>
          </CourseGoalCell>
          <CourseGoalCell>
            <Input
              type="text"
              inputMode="numeric"
              value={value.minBp ?? ""}
              placeholder="-"
              onChange={(e) => {
                onChange({ ...value, minBp: sanitizeBpInput(e.target.value, baseline?.min_bp ?? null) });
              }}
              className="h-9 text-center tabular-nums"
            />
          </CourseGoalCell>
          <CourseGoalCell>
            <Input
              type="text"
              inputMode="decimal"
              value={value.rate ?? ""}
              placeholder="-"
              onChange={(e) => {
                onChange(linkCourseAdjustFromRate(value, sanitizeRateInput(e.target.value, baseline?.rate ?? null)));
              }}
              className="h-9 text-center tabular-nums"
            />
          </CourseGoalCell>
          <CourseGoalCell>
            <select
              value={value.rank}
              onChange={(e) => onChange(linkCourseAdjustFromRank(value, e.target.value))}
              className="h-9 w-full cursor-pointer rounded-md border border-border bg-card px-2 text-center text-caption font-semibold outline-none focus:border-primary"
            >
              {allowedRanks(baseline?.rank ?? null).map((rank) => (
                <option key={rank} value={rank}>{rank}</option>
              ))}
            </select>
          </CourseGoalCell>
        </div>
      </div>

      <DialogFooter className="flex-col items-stretch gap-2 border-t border-border px-0 pt-3 sm:flex-row sm:items-center">
        {hasAnyChange && validation && !validation.ok && (
          <p className="min-w-0 text-caption text-destructive sm:flex-1">
            {formatGoalValidationErrors(validation.errors, t)}
          </p>
        )}
        <div className="ml-auto flex justify-end gap-2">
          <Button onClick={onContinue} disabled={baselineLoading || !hasAnyChange || !validation?.ok}>
            {t("ranking.detail.calculator.setGoalButton")}
          </Button>
        </div>
      </DialogFooter>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <div className="text-caption text-muted-foreground">{label}</div>
      {children}
    </div>
  );
}

interface ConfirmTarget {
  clearType: number | null;
  minBp: number | null;
  rank: string | null;
  rate: number | null;
}

function MetricRow({
  label,
  baselineText,
  targetText,
  state,
}: {
  label: string;
  baselineText: string;
  targetText: string;
  state: "improved" | "regressed" | "same";
}) {
  return (
    <div className="flex items-center justify-between rounded-md bg-secondary/30 px-3 py-1.5 text-label">
      <span className="text-muted-foreground">{label}</span>
      <span className="flex items-center gap-1.5 font-medium tabular-nums">
        <span className="text-muted-foreground">{baselineText}</span>
        <span className="text-muted-foreground">→</span>
        <span
          className={cn(
            state === "improved" && "text-primary",
            state === "regressed" && "text-destructive",
          )}
        >
          {targetText}
        </span>
      </span>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-md bg-secondary/30 px-3 py-1.5 text-label">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

function ConfirmStep({
  goalType,
  chart,
  course,
  clientType,
  baseline,
  baselineLoading,
  target,
  validation,
  showBack,
  onBack,
}: {
  goalType: "chart" | "course";
  chart: GoalDraft | null;
  course: (CourseAdjustDiff & { course: TargetCourse; clientType: string }) | null;
  clientType: string;
  baseline: { clear_type: number | null; min_bp: number | null; rank: string | null; rate: number | null } | null;
  baselineLoading: boolean;
  target: ConfirmTarget;
  validation: { ok: boolean; errors: string[]; improvedMetrics: string[] } | null;
  showBack: boolean;
  onBack: () => void;
}) {
  const { t } = useTranslation();
  const clearLabels = getClientLabels(clientType);
  const title = goalType === "chart" ? chart?.fumen.title : course?.course.name;
  const levelDisplay =
    goalType === "chart" && chart
      ? formatTableLevelWithSymbolForDisplay({ tableSymbol: chart.fumen.symbol, level: chart.fumen.level })
      : null;

  function metricState(metric: string): "improved" | "regressed" | "same" {
    if (!validation) return "same";
    if (validation.improvedMetrics.includes(metric)) return "improved";
    if (validation.errors.some((e) => e.startsWith(metric))) return "regressed";
    return "same";
  }

  return (
    <div className="space-y-4">
      {showBack && <BackButton onClick={onBack} label={t("common.actions.back")} />}

      <div className="flex items-center gap-2">
        {levelDisplay && (
          <span className="rounded-md border border-primary/40 bg-primary/10 px-2 py-0.5 text-caption font-semibold text-primary">
            {levelDisplay}
          </span>
        )}
        {goalType === "course" && course?.course.dan_title && (
          <span className="rounded-md border border-accent/40 bg-accent/10 px-2 py-0.5 text-caption font-semibold text-accent">
            {course.course.dan_title}
          </span>
        )}
        <span className="truncate text-body font-semibold">{title}</span>
      </div>

      <div className="space-y-1.5">
        <div className="text-caption text-muted-foreground">{t("goals.setup.conditions")}</div>
        {baselineLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <>
            <InfoRow label={t("goals.setup.clientType")} value={CLIENT_LABELS[clientType] ?? clientType} />
            {target.clearType != null && (
              <MetricRow
                label={t("common.fields.clear")}
                baselineText={clearLabels[baseline?.clear_type ?? 0] ?? CLEAR_TYPE_LABELS[baseline?.clear_type ?? 0] ?? "-"}
                targetText={clearLabels[target.clearType] ?? CLEAR_TYPE_LABELS[target.clearType] ?? String(target.clearType)}
                state={metricState("clear_type")}
              />
            )}
            {target.minBp != null && (
              <MetricRow
                label="BP"
                baselineText={baseline?.min_bp != null ? String(baseline.min_bp) : "-"}
                targetText={String(target.minBp)}
                state={metricState("min_bp")}
              />
            )}
            {target.rank != null && (
              <MetricRow
                label={t("common.fields.rank")}
                baselineText={baseline?.rank ?? "-"}
                targetText={target.rank}
                state={metricState("rank")}
              />
            )}
            {target.rate != null && (
              <MetricRow
                label={t("common.fields.rate")}
                baselineText={baseline?.rate != null ? formatRatePercent(baseline.rate) : "-"}
                targetText={formatRatePercent(target.rate)}
                state={metricState("rate")}
              />
            )}
          </>
        )}
        {validation && !validation.ok && !baselineLoading && (
          <p className="text-caption text-destructive">{formatGoalValidationErrors(validation.errors, t)}</p>
        )}
      </div>
    </div>
  );
}
