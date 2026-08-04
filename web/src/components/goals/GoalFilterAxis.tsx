"use client";

import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { Check } from "lucide-react";
import { CalendarRangePicker } from "@/components/common/CalendarRangePicker";
import { CLEAR_TYPE_LABELS } from "@/components/charts/ClearDistributionChart";
import type { AxisFacetCounts, AxisFilter, AxisOptions, GoalAxis } from "@/lib/goal-filter-core";
import { isTableEnabled, setExcluded, toggleExcluded } from "@/lib/goal-filter-core";
import { clearTdClass, rankTdClass } from "@/lib/score-cell-class";
import { formatTableLevelWithSymbolForDisplay } from "@/lib/table-level-display";
import { cn } from "@/lib/utils";

interface GoalFilterAxisProps {
  axis: GoalAxis;
  filter: AxisFilter;
  options: AxisOptions;
  counts: AxisFacetCounts;
  /** How many goals on this axis survive the filter — shown next to the title. */
  matchedCount: number;
  onFilterChange: (next: AxisFilter) => void;
  /** The achieved-date range only makes sense on the achieved tab. */
  showAchievedRange: boolean;
}

function sanitizeRate(raw: string): string {
  const cleaned = raw.replace(/[^\d.]/g, "");
  const [head, ...tail] = cleaned.split(".");
  const decimal = tail.join("").slice(0, 2);
  return tail.length > 0 ? `${head.slice(0, 3)}.${decimal}` : head.slice(0, 3);
}

function sanitizeNaturalNumber(raw: string): string {
  return raw.replace(/\D/g, "");
}

function parseBoundedNumber(raw: string, minAllowed: number, maxAllowed?: number): number | null {
  if (raw.trim() === "") return null;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) return null;
  if (parsed < minAllowed) return minAllowed;
  if (maxAllowed != null && parsed > maxAllowed) return maxAllowed;
  return parsed;
}

function rangeInvalid(min: number | null, max: number | null): boolean {
  return min != null && max != null && min > max;
}

// A chip is ON unless the user turned it off — the default state of the whole
// panel is "everything lit", which is what "no filter" means here.
function FilterChip({
  enabled,
  count,
  onClick,
  toneClass,
  activeClass,
  children,
}: {
  enabled: boolean;
  count: number;
  onClick: () => void;
  /** Solid clear/rank cell colouring; omitted for neutral table/level chips. */
  toneClass?: string;
  activeClass: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={enabled}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-caption font-semibold transition-colors",
        enabled ? toneClass ?? activeClass : "border-border bg-transparent text-muted-foreground opacity-50 hover:opacity-80",
        enabled && toneClass && "border-transparent",
      )}
    >
      <span>{children}</span>
      <span className="tabular-nums opacity-75">{count}</span>
    </button>
  );
}

function Field({
  label,
  empty,
  children,
}: {
  label: string;
  /** Renders the "no goal targets this" note instead of the controls. */
  empty?: boolean;
  children: React.ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div className="space-y-1.5">
      <span className="block text-caption font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      {empty ? (
        <p className="text-caption text-muted-foreground/70">{t("goals.filter.noneSpecified")}</p>
      ) : (
        <div className="flex flex-wrap items-center gap-1.5">{children}</div>
      )}
    </div>
  );
}

function NumberRangeInputs({
  min,
  max,
  onMinChange,
  onMaxChange,
  minAllowed,
  maxAllowed,
  integerOnly = false,
}: {
  min: number | null;
  max: number | null;
  onMinChange: (value: number | null) => void;
  onMaxChange: (value: number | null) => void;
  minAllowed: number;
  maxAllowed?: number;
  integerOnly?: boolean;
}) {
  const { t } = useTranslation();
  const invalid = rangeInvalid(min, max);
  const sanitize = integerOnly ? sanitizeNaturalNumber : sanitizeRate;

  // Draft strings decouple keystrokes from the committed numeric filter value,
  // so an in-progress decimal like "12." doesn't get collapsed to "12" mid-typing.
  // External resets (e.g. "reset filters") still need to reach the draft, so we
  // resync during render when the committed prop changes — React's documented
  // pattern for adjusting state from props without an effect.
  const [minDraft, setMinDraft] = useState(min == null ? "" : String(min));
  const [maxDraft, setMaxDraft] = useState(max == null ? "" : String(max));
  const [prevMin, setPrevMin] = useState(min);
  const [prevMax, setPrevMax] = useState(max);

  if (min !== prevMin) {
    setPrevMin(min);
    setMinDraft(min == null ? "" : String(min));
  }
  if (max !== prevMax) {
    setPrevMax(max);
    setMaxDraft(max == null ? "" : String(max));
  }

  const inputClass =
    "h-7 w-20 rounded border bg-input px-2 text-label tabular-nums text-foreground focus:outline-none focus:ring-1";

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1.5">
        <input
          type="text"
          inputMode={integerOnly ? "numeric" : "decimal"}
          aria-label={t("goals.filter.min")}
          placeholder={t("goals.filter.min")}
          value={minDraft}
          onChange={(e) => {
            const next = sanitize(e.target.value);
            setMinDraft(next);
            onMinChange(parseBoundedNumber(next, minAllowed, maxAllowed));
          }}
          onBlur={(e) => onMinChange(parseBoundedNumber(sanitize(e.target.value), minAllowed, maxAllowed))}
          className={cn(
            inputClass,
            invalid ? "border-destructive focus:ring-destructive" : "border-border focus:ring-ring",
          )}
        />
        <span className="text-label text-muted-foreground">~</span>
        <input
          type="text"
          inputMode={integerOnly ? "numeric" : "decimal"}
          aria-label={t("goals.filter.max")}
          placeholder={t("goals.filter.max")}
          value={maxDraft}
          onChange={(e) => {
            const next = sanitize(e.target.value);
            setMaxDraft(next);
            onMaxChange(parseBoundedNumber(next, minAllowed, maxAllowed));
          }}
          onBlur={(e) => onMaxChange(parseBoundedNumber(sanitize(e.target.value), minAllowed, maxAllowed))}
          className={cn(
            inputClass,
            invalid ? "border-destructive focus:ring-destructive" : "border-border focus:ring-ring",
          )}
        />
      </div>
      {invalid && (
        <span className="text-caption font-medium text-destructive">
          {t("goals.filter.invalidRange")}
        </span>
      )}
    </div>
  );
}

/** Every filter row for one axis (chart goals or course goals). */
export function GoalFilterAxis({
  axis,
  filter,
  options,
  counts,
  matchedCount,
  onFilterChange,
  showAchievedRange,
}: GoalFilterAxisProps) {
  const { t } = useTranslation();
  const isCourse = axis === "course";
  const axisTone = isCourse
    ? {
        text: "text-accent",
        bg: "bg-accent/10",
        border: "border-accent/40",
        chip: "border-accent/60 bg-accent/20 text-accent",
        checkbox: "bg-accent text-accent-foreground",
      }
    : {
        text: "text-primary",
        bg: "bg-primary/10",
        border: "border-primary/40",
        chip: "border-primary/60 bg-primary/20 text-primary",
        checkbox: "bg-primary text-primary-foreground",
      };

  function patch(next: Partial<AxisFilter>) {
    onFilterChange({ ...filter, visible: true, ...next });
  }

  function setVisible(visible: boolean) {
    onFilterChange({ ...filter, visible });
  }

  function enableExcludedValue<T>(list: T[], value: T): T[] {
    return list.filter((item) => item !== value);
  }

  const header = (
    <div className={cn("flex items-center justify-between gap-3 rounded-md border px-2.5 py-2", axisTone.bg, axisTone.border)}>
      <span className={cn("text-label font-bold", axisTone.text)}>
        {isCourse ? t("goals.filter.courseAxis") : t("goals.filter.chartAxis")}
        <span className="ml-1.5 font-semibold text-muted-foreground tabular-nums">
          {matchedCount}
        </span>
      </span>
      <button
        type="button"
        aria-pressed={filter.visible !== false}
        onClick={() => setVisible(filter.visible === false)}
        className="inline-flex shrink-0 items-center gap-1.5 text-caption font-semibold text-muted-foreground transition-colors hover:text-foreground"
      >
        <span>{t("goals.filter.showAxis")}</span>
        <span
          className={cn(
            "inline-flex h-4 w-4 items-center justify-center rounded-sm border",
            filter.visible === false
              ? "border-muted-foreground/40 bg-transparent"
              : cn("border-transparent", axisTone.checkbox),
          )}
        >
          {filter.visible !== false && <Check className="h-3 w-3" />}
        </span>
      </button>
    </div>
  );
  const activeClass = axisTone.chip;
  const axisVisible = filter.visible !== false;

  if (options.goalCount === 0) {
    return (
      <div className="min-w-0 flex-1 space-y-3">
        {header}
        <p className="text-caption text-muted-foreground/70">{t("goals.filter.axisEmpty")}</p>
      </div>
    );
  }

  return (
    <div className="min-w-0 flex-1 space-y-3">
      {header}

      <Field label={t("goals.filter.table")} empty={options.tables.length === 0}>
        {options.tables.map((table) => {
          const levelKeys = (table.levels ?? []).map((level) => level.key);
          const enabled = isCourse
            ? !filter.excludedTables.includes(table.slug)
            : isTableEnabled(levelKeys, filter);
          return (
            <FilterChip
              key={table.slug}
              enabled={axisVisible && enabled}
              count={counts.tables[table.slug] ?? 0}
              activeClass={activeClass}
              onClick={() =>
                isCourse
                  ? patch({
                      excludedTables: axisVisible
                        ? toggleExcluded(filter.excludedTables, table.slug)
                        : enableExcludedValue(filter.excludedTables, table.slug),
                    })
                  : patch({
                      excludedLevels: axisVisible
                        ? setExcluded(filter.excludedLevels, levelKeys, enabled)
                        : setExcluded(filter.excludedLevels, levelKeys, false),
                    })
              }
            >
              {table.symbol ? `${table.symbol} ${table.name}` : table.name}
            </FilterChip>
          );
        })}
      </Field>

      {!isCourse && (
        <Field label={t("goals.filter.level")} empty={options.tables.length === 0}>
          {options.tables.flatMap((table) =>
            (table.levels ?? []).map((level) => (
              <FilterChip
                key={level.key}
                enabled={axisVisible && !filter.excludedLevels.includes(level.key)}
                count={counts.levels?.[level.key] ?? 0}
                activeClass={activeClass}
                onClick={() =>
                  patch({
                    excludedLevels: axisVisible
                      ? toggleExcluded(filter.excludedLevels, level.key)
                      : enableExcludedValue(filter.excludedLevels, level.key),
                  })
                }
              >
                {formatTableLevelWithSymbolForDisplay({
                  tableSlug: table.slug,
                  tableSymbol: table.symbol,
                  level: level.level,
                })}
              </FilterChip>
            )),
          )}
        </Field>
      )}

      <Field label={t("goals.filter.clear")} empty={options.clearTypes.length === 0}>
        {options.clearTypes.map((clearType) => {
          const enabled = !filter.excludedClearTypes.includes(clearType);
          return (
            <FilterChip
              key={clearType}
              enabled={axisVisible && enabled}
              count={counts.clearTypes[clearType] ?? 0}
              toneClass={clearTdClass(clearType)}
              activeClass={activeClass}
              onClick={() =>
                patch({
                  excludedClearTypes: axisVisible
                    ? toggleExcluded(filter.excludedClearTypes, clearType)
                    : enableExcludedValue(filter.excludedClearTypes, clearType),
                })
              }
            >
              {CLEAR_TYPE_LABELS[clearType] ?? String(clearType)}
            </FilterChip>
          );
        })}
      </Field>

      <Field label={t("goals.filter.rank")} empty={options.ranks.length === 0}>
        {options.ranks.map((rank) => (
          <FilterChip
            key={rank}
            enabled={axisVisible && !filter.excludedRanks.includes(rank)}
            count={counts.ranks[rank] ?? 0}
            toneClass={rankTdClass(rank)}
            activeClass={activeClass}
            onClick={() =>
              patch({
                excludedRanks: axisVisible
                  ? toggleExcluded(filter.excludedRanks, rank)
                  : enableExcludedValue(filter.excludedRanks, rank),
              })
            }
          >
            {rank}
          </FilterChip>
        ))}
      </Field>

      <div className="flex flex-wrap gap-x-8 gap-y-3">
        <Field label={t("goals.filter.rate")} empty={!options.hasRate}>
          <NumberRangeInputs
            min={filter.rateMin}
            max={filter.rateMax}
            minAllowed={0}
            maxAllowed={100}
            onMinChange={(value) => patch({ rateMin: value })}
            onMaxChange={(value) => patch({ rateMax: value })}
          />
        </Field>
        <Field label={t("goals.filter.bp")} empty={!options.hasBp}>
          <NumberRangeInputs
            min={filter.bpMin}
            max={filter.bpMax}
            minAllowed={0}
            integerOnly
            onMinChange={(value) => patch({ bpMin: value })}
            onMaxChange={(value) => patch({ bpMax: value })}
          />
        </Field>
      </div>

      <div className="flex flex-wrap gap-x-8 gap-y-3">
        <Field label={t("goals.filter.createdRange")}>
          <CalendarRangePicker
            label={t("goals.filter.anyDate")}
            value={{ from: filter.createdFrom, to: filter.createdTo }}
            onChange={(next) => patch({ createdFrom: next.from, createdTo: next.to })}
          />
        </Field>
        {showAchievedRange && (
          <Field label={t("goals.filter.achievedRange")}>
            <CalendarRangePicker
              label={t("goals.filter.anyDate")}
              value={{ from: filter.achievedFrom, to: filter.achievedTo }}
              onChange={(next) => patch({ achievedFrom: next.from, achievedTo: next.to })}
            />
          </Field>
        )}
      </div>
    </div>
  );
}
