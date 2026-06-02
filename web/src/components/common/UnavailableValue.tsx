"use client";

import { useTranslation } from "react-i18next";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ARRANGEMENT_REASON_I18N_KEY } from "@/lib/score-row-detail-core.mjs";

interface UnavailableValueProps {
  /** The unavailable reason code, or null to render a plain "--". */
  reason: string | null;
}

/**
 * Renders a "--●" placeholder that mirrors the tooltip-dot pattern used
 * across the dashboard tables. When `reason` is provided, a tooltip
 * shows the localised explanation; otherwise just "--" is rendered.
 */
export function UnavailableValue({ reason }: UnavailableValueProps) {
  const { t } = useTranslation();

  const inner = (
    <span className="cursor-default text-muted-foreground row-muted">
      --
      {reason !== null && (
        <span className="ml-0.5 text-accent/70 leading-none">●</span>
      )}
    </span>
  );

  if (reason === null) return inner;

  const i18nKey =
    ARRANGEMENT_REASON_I18N_KEY[reason] ??
    `fumenRowDetail.unavailableReason.${reason}`;

  return (
    <TooltipProvider delayDuration={100}>
      <Tooltip>
        <TooltipTrigger asChild>{inner}</TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs text-label">
          {t(i18nKey)}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
