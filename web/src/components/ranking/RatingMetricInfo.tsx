"use client";

import type { ReactNode } from "react";
import { Info } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export type RatingMetricKey = "exp" | "rating" | "bmsforce" | "level" | "level_mult";

export function MetricInfoIcon({ metric }: { metric: RatingMetricKey }) {
  const { t } = useTranslation();

  function ariaLabel(): string {
    switch (metric) {
      case "exp": return t("ranking.metricInfo.expAria");
      case "level": return t("ranking.metricInfo.levelAria");
      case "rating": return t("ranking.metricInfo.ratingAria");
      case "level_mult": return t("ranking.metricInfo.levelMultAria");
      case "bmsforce": return t("ranking.metricInfo.bmsforceAria");
    }
  }

  function renderContent(): ReactNode {
    if (metric === "bmsforce") {
      return (
        <div className="space-y-2">
          <p>{t("ranking.metricInfo.bmsforceContent")}</p>
          <p className="text-caption text-muted-foreground">
            Level multiplier: {t("ranking.metricInfo.levelMultContent")}
          </p>
        </div>
      );
    }
    switch (metric) {
      case "exp": return <p>{t("ranking.metricInfo.expContent")}</p>;
      case "level": return <p>{t("ranking.metricInfo.levelContent")}</p>;
      case "rating": return <p>{t("ranking.metricInfo.ratingContent")}</p>;
      case "level_mult": return <p>{t("ranking.metricInfo.levelMultContent")}</p>;
    }
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={ariaLabel()}
          onClick={(event) => event.stopPropagation()}
          onKeyDown={(event) => event.stopPropagation()}
          className="ml-1.5 inline-flex items-center rounded-sm align-middle cursor-help focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          <Info className="h-3.5 w-3.5 text-muted-foreground" />
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs text-label leading-relaxed pointer-events-auto">
        {renderContent()}
      </TooltipContent>
    </Tooltip>
  );
}
