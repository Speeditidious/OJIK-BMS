"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronLeft, Loader2, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { CLEAR_TYPE_LABELS } from "@/components/charts/ClearDistributionChart";
import {
  RatingCalculatorDialog,
  RATING_CLEAR_TYPES,
  getClientLabels,
  rankGradeFromRate,
} from "@/components/ranking/RatingCalculatorDialog";
import { useRankingTables, useRankingContributionRows } from "@/hooks/use-rankings";
import { useCreateGoal, useGoalBaseline, useGoals, useTargetCourses, type TargetCourse } from "@/hooks/use-goals";
import type { GoalDraft } from "@/lib/goal-types";
import { validateGoalTarget } from "@/lib/goal-validation-core.mjs";
import { anyTextMatchesLooseQuery } from "@/lib/text-search-core.mjs";
import { formatRatePercent } from "@/lib/rate-format";
import { formatTableLevelWithSymbolForDisplay } from "@/lib/table-level-display";
import { cn } from "@/lib/utils";

const CLIENT_TYPES = ["lr2", "beatoraja", "qwilight"] as const;
const CLIENT_LABELS: Record<string, string> = { lr2: "LR2", beatoraja: "Beatoraja", qwilight: "Qwilight" };

type Step = "type" | "table" | "chart-pick" | "adjust-chart" | "course-pick" | "adjust-course" | "confirm";

interface CourseAdjust {
  clearType: number;
  minBp: number | null;
  rate: number | null;
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

  const [pendingChart, setPendingChart] = useState<GoalDraft | null>(null);
  const [chartPickCurrent, setChartPickCurrent] = useState<{
    fumen: GoalDraft["fumen"];
    current: { clearType: number | null; rank: string | null; minBp: number | null; rate: number | null };
    defaultClientType: string;
  } | null>(null);

  const [pendingCourseTarget, setPendingCourseTarget] = useState<TargetCourse | null>(null);
  const [courseAdjust, setCourseAdjust] = useState<CourseAdjust>({ clearType: 1, minBp: 0, rate: 0 });
  const [pendingCourse, setPendingCourse] = useState<
    (CourseAdjust & { course: TargetCourse; rank: string; clientType: string }) | null
  >(null);

  const [clientType, setClientType] = useState<string>("beatoraja");
  const [serverError, setServerError] = useState<string | null>(null);

  const activeGoalsQuery = useGoals("active", open);
  const defaultClientType = activeGoalsQuery.data?.default_client_type ?? null;

  const createGoal = useCreateGoal();

  // Reset all wizard state whenever the dialog (re)opens.
  useEffect(() => {
    if (!open) return;
    setServerError(null);
    if (initialDraft) {
      setPendingChart(initialDraft);
      setPendingCourseTarget(null);
      setPendingCourse(null);
      setClientType(initialDraft.clientType || defaultClientType || "beatoraja");
      setStep("confirm");
    } else {
      setStep("type");
      setSelectedTableSlug(null);
      setChartSearch("");
      setCourseSearch("");
      setPendingChart(null);
      setChartPickCurrent(null);
      setPendingCourseTarget(null);
      setPendingCourse(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initialDraft]);

  const rankingTablesQuery = useRankingTables();

  const chartRowsQuery = useRankingContributionRows({
    tableSlug: selectedTableSlug,
    metric: "rating",
    scope: "all",
    sortBy: "value",
    sortDir: "desc",
    enabled: step === "chart-pick" && !!selectedTableSlug,
  });
  const filteredChartRows = useMemo(() => {
    const entries = chartRowsQuery.data?.entries ?? [];
    if (!chartSearch.trim()) return entries;
    return entries.filter((e) => anyTextMatchesLooseQuery([e.title, e.artist], chartSearch));
  }, [chartRowsQuery.data, chartSearch]);

  const targetCoursesQuery = useTargetCourses(step === "course-pick");
  const { recognizedCourses, unrecognizedCourses } = useMemo(() => {
    const courses = targetCoursesQuery.data?.courses ?? [];
    const filtered = courseSearch.trim()
      ? courses.filter((c) => anyTextMatchesLooseQuery([c.name, c.dan_title], courseSearch))
      : courses;
    return {
      recognizedCourses: filtered.filter((c) => c.is_recognized),
      unrecognizedCourses: filtered.filter((c) => !c.is_recognized),
    };
  }, [targetCoursesQuery.data, courseSearch]);

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
    setStep("adjust-chart");
  }

  function handleCalculatorSetGoal(draft: GoalDraft) {
    setPendingChart(draft);
    setClientType(draft.clientType || defaultClientType || "beatoraja");
    setStep("confirm");
  }

  function handleSelectCourse(course: TargetCourse) {
    setPendingCourseTarget(course);
    setCourseAdjust({ clearType: 1, minBp: 0, rate: 0 });
    setStep("adjust-course");
  }

  function handleCourseAdjustContinue() {
    if (!pendingCourseTarget) return;
    const rank = rankGradeFromRate(courseAdjust.rate);
    setPendingCourse({ ...courseAdjust, course: pendingCourseTarget, rank, clientType: defaultClientType ?? "beatoraja" });
    setClientType(defaultClientType ?? "beatoraja");
    setStep("confirm");
  }

  function handleSave() {
    setServerError(null);
    const payload = {
      goal_type: goalType!,
      client_type: clientType,
      table_slug: pendingChart?.tableSlug ?? null,
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
        setServerError(err instanceof Error ? err.message : t("goals.setup.saveError"));
      },
    });
  }

  const wizardOpen = open && step !== "adjust-chart";

  return (
    <>
      <Dialog open={wizardOpen} onOpenChange={(next) => !next && handleClose()}>
        <DialogContent className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden">
          <DialogHeader>
            <DialogTitle>{t("goals.setup.title")}</DialogTitle>
          </DialogHeader>

          <div className="flex-1 space-y-4 overflow-y-auto py-2">
            {step === "type" && (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => setStep("table")}
                  className="rounded-xl border border-border bg-card p-6 text-left transition-colors hover:border-primary hover:bg-primary/5"
                >
                  <div className="text-body font-semibold">{t("goals.setup.chartType")}</div>
                  <div className="mt-1 text-caption text-muted-foreground">{t("goals.setup.chartTypeDescription")}</div>
                </button>
                <button
                  type="button"
                  onClick={() => setStep("course-pick")}
                  className="rounded-xl border border-border bg-card p-6 text-left transition-colors hover:border-primary hover:bg-primary/5"
                >
                  <div className="text-body font-semibold">{t("goals.setup.courseType")}</div>
                  <div className="mt-1 text-caption text-muted-foreground">{t("goals.setup.courseTypeDescription")}</div>
                </button>
              </div>
            )}

            {step === "table" && (
              <div className="space-y-2">
                <BackButton onClick={() => setStep("type")} label={t("common.actions.back")} />
                {rankingTablesQuery.isLoading ? (
                  <Skeleton className="h-40 w-full" />
                ) : (
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                    {(rankingTablesQuery.data ?? []).map((table) => (
                      <button
                        key={table.slug}
                        type="button"
                        onClick={() => handleSelectTable(table.slug)}
                        className="rounded-lg border border-border bg-card px-3 py-2 text-left text-label font-medium transition-colors hover:border-primary hover:bg-primary/5"
                      >
                        {table.display_name}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {step === "chart-pick" && (
              <div className="space-y-2">
                <BackButton onClick={() => setStep("table")} label={t("common.actions.back")} />
                <label className="relative block">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    value={chartSearch}
                    onChange={(e) => setChartSearch(e.target.value)}
                    placeholder={t("ranking.detail.searchPlaceholder")}
                    className="w-full rounded-lg border border-border bg-card px-9 py-2 text-body outline-none transition-colors focus:border-primary"
                  />
                </label>
                <div className="max-h-96 space-y-1 overflow-y-auto">
                  {chartRowsQuery.isLoading ? (
                    <Skeleton className="h-40 w-full" />
                  ) : filteredChartRows.length === 0 ? (
                    <p className="py-6 text-center text-body text-muted-foreground">{t("common.states.noRecords")}</p>
                  ) : (
                    filteredChartRows.map((entry) => (
                      <button
                        key={`${entry.sha256 ?? ""}-${entry.md5 ?? ""}`}
                        type="button"
                        onClick={() => handleSelectChart(entry)}
                        className="flex w-full items-center gap-3 rounded-lg border border-transparent px-3 py-2 text-left transition-colors hover:border-primary hover:bg-primary/5"
                      >
                        <span className="shrink-0 rounded-md border border-primary/40 bg-primary/10 px-1.5 py-0.5 text-caption font-semibold text-primary">
                          {formatTableLevelWithSymbolForDisplay({ tableSymbol: entry.symbol, level: entry.level })}
                        </span>
                        <span className="min-w-0 flex-1 truncate text-body">{entry.title}</span>
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}

            {step === "course-pick" && (
              <div className="space-y-2">
                <BackButton onClick={() => setStep("type")} label={t("common.actions.back")} />
                <label className="relative block">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    value={courseSearch}
                    onChange={(e) => setCourseSearch(e.target.value)}
                    placeholder={t("ranking.detail.searchPlaceholder")}
                    className="w-full rounded-lg border border-border bg-card px-9 py-2 text-body outline-none transition-colors focus:border-primary"
                  />
                </label>
                <div className="max-h-96 space-y-3 overflow-y-auto">
                  {targetCoursesQuery.isLoading ? (
                    <Skeleton className="h-40 w-full" />
                  ) : (
                    <>
                      <CourseGroup
                        label={t("goals.setup.recognizedCourses")}
                        courses={recognizedCourses}
                        onSelect={handleSelectCourse}
                      />
                      <CourseGroup
                        label={t("goals.setup.unrecognizedCourses")}
                        courses={unrecognizedCourses}
                        onSelect={handleSelectCourse}
                      />
                    </>
                  )}
                </div>
              </div>
            )}

            {step === "adjust-course" && pendingCourseTarget && (
              <CourseAdjustPanel
                course={pendingCourseTarget}
                value={courseAdjust}
                onChange={setCourseAdjust}
                onBack={() => setStep("course-pick")}
                onContinue={handleCourseAdjustContinue}
              />
            )}

            {step === "confirm" && goalType && (
              <ConfirmStep
                goalType={goalType}
                chart={pendingChart}
                course={pendingCourse}
                clientType={clientType}
                onClientTypeChange={setClientType}
                baseline={baselineQuery.data ?? null}
                baselineLoading={baselineQuery.isLoading}
                target={target}
                validation={validation}
                showBack={!initialDraft}
                onBack={() => setStep(goalType === "chart" ? "chart-pick" : "course-pick")}
              />
            )}
          </div>

          {step === "confirm" && goalType && (
            <DialogFooter className="flex-col items-stretch gap-2 sm:flex-row sm:items-center sm:justify-between">
              {serverError && <p className="text-caption text-destructive">{serverError}</p>}
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={handleClose} disabled={createGoal.isPending}>
                  {t("common.actions.cancel")}
                </Button>
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
          onClose={() => setStep("chart-pick")}
          tableSlug={selectedTableSlug ?? ""}
          fumen={chartPickCurrent.fumen}
          current={chartPickCurrent.current}
          clientType={chartPickCurrent.defaultClientType}
          titleOverride={t("goals.setup.title")}
          onSetGoal={handleCalculatorSetGoal}
        />
      )}
    </>
  );
}

function BackButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <Button variant="ghost" size="sm" className="-ml-2 gap-1 text-muted-foreground" onClick={onClick}>
      <ChevronLeft className="h-4 w-4" />
      {label}
    </Button>
  );
}

function CourseGroup({
  label,
  courses,
  onSelect,
}: {
  label: string;
  courses: TargetCourse[];
  onSelect: (course: TargetCourse) => void;
}) {
  if (courses.length === 0) return null;
  return (
    <div className="space-y-1">
      <div className="text-caption font-semibold uppercase tracking-wide text-muted-foreground">{label}</div>
      {courses.map((course) => (
        <button
          key={course.course_id}
          type="button"
          onClick={() => onSelect(course)}
          className="flex w-full items-center gap-2 rounded-lg border border-transparent px-3 py-2 text-left transition-colors hover:border-primary hover:bg-primary/5"
        >
          {course.dan_title && (
            <span className="shrink-0 rounded-md border border-accent/40 bg-accent/10 px-1.5 py-0.5 text-caption font-semibold text-accent">
              {course.dan_title}
            </span>
          )}
          <span className="min-w-0 flex-1 truncate text-body">{course.name}</span>
        </button>
      ))}
    </div>
  );
}

function CourseAdjustPanel({
  course,
  value,
  onChange,
  onBack,
  onContinue,
}: {
  course: TargetCourse;
  value: CourseAdjust;
  onChange: (next: CourseAdjust) => void;
  onBack: () => void;
  onContinue: () => void;
}) {
  const { t } = useTranslation();
  const derivedRank = rankGradeFromRate(value.rate);

  return (
    <div className="space-y-4">
      <BackButton onClick={onBack} label={t("common.actions.back")} />
      <div className="text-body font-semibold">{course.name}</div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label={t("common.fields.clear")}>
          <select
            value={value.clearType}
            onChange={(e) => onChange({ ...value, clearType: Number(e.target.value) })}
            className="h-9 w-full cursor-pointer rounded-md border border-border bg-card px-2 text-center text-caption font-semibold outline-none focus:border-primary"
          >
            {RATING_CLEAR_TYPES.map((ct) => (
              <option key={ct} value={ct}>
                {CLEAR_TYPE_LABELS[ct] ?? String(ct)}
              </option>
            ))}
          </select>
        </Field>
        <Field label="BP">
          <Input
            type="number"
            min={0}
            value={value.minBp ?? 0}
            onChange={(e) => {
              const next = Number(e.target.value);
              onChange({ ...value, minBp: Number.isFinite(next) ? Math.max(0, Math.trunc(next)) : 0 });
            }}
            className="h-9 text-center tabular-nums"
          />
        </Field>
        <Field label={t("common.fields.rate")}>
          <Input
            type="number"
            min={0}
            max={100}
            step={0.01}
            value={value.rate ?? 0}
            onChange={(e) => {
              const next = Number(e.target.value);
              onChange({ ...value, rate: Number.isFinite(next) ? Math.min(100, Math.max(0, next)) : 0 });
            }}
            className="h-9 text-center tabular-nums"
          />
        </Field>
        <Field label={t("common.fields.rank")}>
          <div className="flex h-9 items-center justify-center rounded-md border border-border bg-secondary/30 text-caption font-semibold">
            {derivedRank}
          </div>
        </Field>
      </div>

      <div className="flex justify-end">
        <Button onClick={onContinue}>{t("common.actions.next")}</Button>
      </div>
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

function ConfirmStep({
  goalType,
  chart,
  course,
  clientType,
  onClientTypeChange,
  baseline,
  baselineLoading,
  target,
  validation,
  showBack,
  onBack,
}: {
  goalType: "chart" | "course";
  chart: GoalDraft | null;
  course: (CourseAdjust & { course: TargetCourse; rank: string; clientType: string }) | null;
  clientType: string;
  onClientTypeChange: (v: string) => void;
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

      <div className="space-y-1">
        <div className="text-caption text-muted-foreground">{t("goals.setup.clientType")}</div>
        <div className="flex gap-2">
          {CLIENT_TYPES.map((ct) => (
            <button
              key={ct}
              type="button"
              onClick={() => onClientTypeChange(ct)}
              className={cn(
                "rounded-md border px-3 py-1.5 text-caption font-semibold transition-colors",
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

      <div className="space-y-1.5">
        <div className="text-caption text-muted-foreground">{t("goals.setup.conditions")}</div>
        {baselineLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <>
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
          <p className="text-caption text-destructive">{t(`goals.setup.errors.${validation.errors[0]}`)}</p>
        )}
      </div>
    </div>
  );
}
