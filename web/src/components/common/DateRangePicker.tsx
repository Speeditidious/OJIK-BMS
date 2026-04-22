"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import {
  type DateRange,
  type RangePreset,
  PRESET_LABELS,
  clampRange,
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

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function DateRangePicker({
  value,
  onChange,
  maxDays = 730,
  className,
}: DateRangePickerProps) {
  // Local draft for custom date inputs — tracks the incoming range so we can
  // reset when the parent changes the range (e.g. switching between presets)
  const [localFrom, setLocalFrom] = useState(value.range.from);
  const [localTo, setLocalTo] = useState(value.range.to);
  const [trackedFrom, setTrackedFrom] = useState(value.range.from);
  const [trackedTo, setTrackedTo] = useState(value.range.to);
  const [error, setError] = useState<string | null>(null);
  const fromRef = useRef<HTMLInputElement>(null);

  // React-idiomatic way to sync derived state: compare during render and
  // enqueue a correction if the parent-controlled range changed.
  // This is the pattern recommended by the React docs (getDerivedStateFromProps equivalent).
  if (trackedFrom !== value.range.from || trackedTo !== value.range.to) {
    setTrackedFrom(value.range.from);
    setTrackedTo(value.range.to);
    setLocalFrom(value.range.from);
    setLocalTo(value.range.to);
    setError(null);
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
      setError("시작 날짜는 끝 날짜보다 앞이어야 합니다.");
      return;
    }

    const clamped = clampRange({ from, to: clampedTo }, maxDays);
    setError(null);
    onChange({ preset: "custom", range: clamped });
  }

  const isCustom = value.preset === "custom";
  const errorId = "date-range-picker-error";

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {/* Preset buttons */}
      <div
        role="group"
        aria-label="날짜 범위 프리셋"
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
            {PRESET_LABELS[preset]}
          </button>
        ))}
      </div>

      {/* Custom date inputs — only shown in custom mode */}
      {isCustom && (
        <div
          className="flex flex-wrap items-center gap-2"
          aria-describedby={error ? errorId : undefined}
        >
          <input
            ref={fromRef}
            type="date"
            aria-label="시작 날짜"
            aria-invalid={!!error}
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
            aria-label="끝 날짜"
            aria-invalid={!!error}
            value={localTo}
            max={todayIso()}
            onChange={(e) => setLocalTo(e.target.value)}
            onBlur={() => commitCustom(localFrom, localTo)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitCustom(localFrom, localTo);
            }}
            className="h-7 rounded border border-border bg-input px-2 text-label text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
          {error && (
            <p
              id={errorId}
              role="alert"
              className="w-full text-caption text-destructive"
            >
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
