"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import {
  type DateRange,
  type RangePreset,
  clampRange,
  getPresetLabel,
  rangeFromPreset,
} from "@/lib/date-range";

export interface DateRangeValue {
  preset: RangePreset;
  range: DateRange;
}

interface DateRangePickerProps {
  value: DateRangeValue;
  onChange: (next: DateRangeValue) => void;
  maxDays?: number;
  className?: string;
}

const PRESETS: RangePreset[] = ["week", "month", "3month", "year", "custom"];
const INVALID_ORDER_ERROR_KEY = "format.dateRange.invalidOrder";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function DateRangePicker({
  value,
  onChange,
  maxDays = 730,
  className,
}: DateRangePickerProps) {
  const { t } = useTranslation();
  // Local draft for custom date inputs — tracks the incoming range so we can
  // reset when the parent changes the range (e.g. switching between presets)
  const [localFrom, setLocalFrom] = useState(value.range.from);
  const [localTo, setLocalTo] = useState(value.range.to);
  const [trackedFrom, setTrackedFrom] = useState(value.range.from);
  const [trackedTo, setTrackedTo] = useState(value.range.to);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const fromRef = useRef<HTMLInputElement>(null);

  // React-idiomatic way to sync derived state: compare during render and
  // enqueue a correction if the parent-controlled range changed.
  // This is the pattern recommended by the React docs (getDerivedStateFromProps equivalent).
  if (trackedFrom !== value.range.from || trackedTo !== value.range.to) {
    setTrackedFrom(value.range.from);
    setTrackedTo(value.range.to);
    setLocalFrom(value.range.from);
    setLocalTo(value.range.to);
    setErrorKey(null);
  }

  // Focus "from" input when entering custom mode
  useEffect(() => {
    if (value.preset === "custom") {
      const id = setTimeout(() => fromRef.current?.focus(), 50);
      return () => clearTimeout(id);
    }
  }, [value.preset]);

  function handlePresetClick(preset: RangePreset) {
    if (preset === "custom") {
      onChange({ preset: "custom", range: value.range });
      return;
    }
    const range = rangeFromPreset(preset);
    onChange({ preset, range });
  }

  function commitCustom(from: string, to: string) {
    const today = todayIso();
    const clampedTo = to > today ? today : to;

    if (!from || !clampedTo) return;
    if (from > clampedTo) {
      setErrorKey(INVALID_ORDER_ERROR_KEY);
      return;
    }

    const clamped = clampRange({ from, to: clampedTo }, maxDays);
    setErrorKey(null);
    onChange({ preset: "custom", range: clamped });
  }

  const isCustom = value.preset === "custom";
  const errorId = "date-range-picker-error";

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {/* Preset buttons */}
      <div
        role="group"
        aria-label={t("format.dateRange.presetLabel")}
        className="flex gap-1"
      >
        {PRESETS.map((preset) => (
          <button
            key={preset}
            type="button"
            aria-pressed={value.preset === preset}
            onClick={() => handlePresetClick(preset)}
            className={cn(
              "h-7 rounded px-2 text-label transition-colors",
              value.preset === preset
                ? "bg-secondary text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {getPresetLabel(preset, t)}
          </button>
        ))}
      </div>

      {/* Custom date inputs — only shown in custom mode */}
      {isCustom && (
        <div
          className="flex flex-wrap items-center gap-2"
          aria-describedby={errorKey ? errorId : undefined}
        >
          <input
            ref={fromRef}
            type="date"
            aria-label={t("format.dateRange.startDate")}
            aria-invalid={!!errorKey}
            value={localFrom}
            max={todayIso()}
            onChange={(e) => setLocalFrom(e.target.value)}
            onBlur={() => commitCustom(localFrom, localTo)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitCustom(localFrom, localTo);
            }}
            className="h-7 rounded border border-border bg-input px-2 text-label text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <span className="text-label text-muted-foreground">~</span>
          <input
            type="date"
            aria-label={t("format.dateRange.endDate")}
            aria-invalid={!!errorKey}
            value={localTo}
            max={todayIso()}
            onChange={(e) => setLocalTo(e.target.value)}
            onBlur={() => commitCustom(localFrom, localTo)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitCustom(localFrom, localTo);
            }}
            className="h-7 rounded border border-border bg-input px-2 text-label text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
          {errorKey && (
            <p
              id={errorId}
              role="alert"
              className="w-full text-caption text-destructive"
            >
              {t(errorKey)}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
