"use client";

import type { ReactNode } from "react";
import { Info } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export type RatingMetricKey = "exp" | "rating" | "bmsforce" | "level" | "level_mult";

interface RatingMetricCopy {
  ariaLabel: string;
  content: string;
}

export const RATING_METRIC_COPY: Record<Exclude<RatingMetricKey, "bmsforce">, RatingMetricCopy> = {
  exp: {
    ariaLabel: "경험치 계산 방식 보기",
    content: "플레이한 모든 차분의 레이팅을 전부 합산한 값. 상위 N개 제한 없이 누적됩니다.",
  },
  level: {
    ariaLabel: "레벨 계산 방식 보기",
    content: "경험치 누적값에 따른 등급. 다음 레벨업에 필요한 경험치 = 다음 레벨 × 200",
  },
  rating: {
    ariaLabel: "레이팅 계산 방식 보기",
    content: "레이팅 상위 TOP N개를 합산한 값.",
  },
  level_mult: {
    ariaLabel: "레벨 가산치 계산 방식 보기",
    content: "1 + 레벨 × 0.01%. 최대 레벨에 도달한 뒤에는 이 가산치가 더 이상 증가하지 않습니다.",
  },
};

function renderMetricContent(metric: RatingMetricKey): ReactNode {
  if (metric === "bmsforce") {
    return (
      <div className="space-y-2">
        <p>
          TOP N 레이팅 합산에 레벨 가산치를 곱한 값을
          표준화한 종합 레이팅. TOP N이 전부 1000점(합산 100,000)일 때 20.0이며, 이후부터는 상승폭이 감소합니다.
        </p>
        <p className="text-caption text-muted-foreground">
          레벨 가산치: {RATING_METRIC_COPY.level_mult.content}
        </p>
      </div>
    );
  }

  return <p>{RATING_METRIC_COPY[metric].content}</p>;
}

function ariaLabelForMetric(metric: RatingMetricKey): string {
  if (metric === "bmsforce") {
    return "BMSFORCE 계산 방식 보기";
  }
  return RATING_METRIC_COPY[metric].ariaLabel;
}

export function MetricInfoIcon({ metric }: { metric: RatingMetricKey }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={ariaLabelForMetric(metric)}
          onClick={(event) => event.stopPropagation()}
          onKeyDown={(event) => event.stopPropagation()}
          className="ml-1.5 inline-flex items-center rounded-sm align-middle cursor-help focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          <Info className="h-3.5 w-3.5 text-muted-foreground" />
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs text-label leading-relaxed pointer-events-auto">
        {renderMetricContent(metric)}
      </TooltipContent>
    </Tooltip>
  );
}
