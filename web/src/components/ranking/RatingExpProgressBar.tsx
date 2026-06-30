"use client";

import { useTranslation } from "react-i18next";

interface RatingExpProgressBarProps {
  progressRatio: number;
  expToNextLevel: number;
  previousProgressRatio?: number | null;
  previousLevel?: number | null;
  currentLevel?: number | null;
  isMaxLevel?: boolean;
  maxLevel?: number;
  /** Signed EXP gained since the previous snapshot; shown above the bar's right edge. */
  expDelta?: number | null;
}

export function RatingExpProgressBar({
  progressRatio,
  expToNextLevel,
  previousProgressRatio,
  previousLevel,
  currentLevel,
  isMaxLevel = false,
  maxLevel,
  expDelta = null,
}: RatingExpProgressBarProps) {
  const { t } = useTranslation();
  const clampedProgress = isMaxLevel ? 1 : Math.max(0, Math.min(progressRatio, 1));
  const clampedPrevious = previousProgressRatio == null
    ? null
    : Math.max(0, Math.min(previousProgressRatio, 1));
  const levelChanged = previousLevel != null && currentLevel != null && previousLevel !== currentLevel;
  const showDelta = clampedPrevious != null;

  let baseRatio = clampedProgress;
  let deltaStart = 0;
  let deltaWidth = 0;

  if (levelChanged) {
    baseRatio = 0;
    deltaWidth = clampedProgress;
  } else if (showDelta) {
    baseRatio = clampedPrevious ?? 0;
    deltaStart = clampedPrevious ?? 0;
    deltaWidth = Math.max(clampedProgress - (clampedPrevious ?? 0), 0);
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-3">
        {isMaxLevel ? (
          <span className="inline-flex items-center rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-caption font-medium text-primary">
            {t("ranking.detail.maxLevel")}{maxLevel != null ? ` · Lv.${maxLevel}` : ""}
          </span>
        ) : (
          <p className="text-caption text-muted-foreground">
            {t("ranking.detail.expToNextLevel", { value: Math.max(0, Math.ceil(expToNextLevel)).toLocaleString() })}
          </p>
        )}
        <div className="flex items-center gap-2 shrink-0">
          {levelChanged && (
            <span className="inline-flex items-center rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-caption font-medium text-primary">
              Lv.{previousLevel} ▶ Lv.{currentLevel}
            </span>
          )}
          {expDelta != null && Math.abs(expDelta) > 1e-9 && (
            <span className="text-caption font-bold tabular-nums" style={{ color: "hsl(var(--primary))" }}>
              {expDelta > 0 ? "+" : ""}{Math.round(expDelta).toLocaleString()}
            </span>
          )}
        </div>
      </div>
      <div className="relative h-2.5 overflow-hidden rounded-full bg-secondary ring-1 ring-border/60">
        <div
          className="absolute inset-y-0 left-0 bg-primary transition-[width] duration-300"
          style={{ width: `${baseRatio * 100}%` }}
        />
        {showDelta && deltaWidth > 0 && (
          <div
            className="absolute inset-y-0 bg-accent ring-1 ring-inset ring-white/25"
            style={{
              left: `${deltaStart * 100}%`,
              width: `${deltaWidth * 100}%`,
            }}
          />
        )}
      </div>
    </div>
  );
}
