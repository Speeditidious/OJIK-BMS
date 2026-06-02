"use client";

import { useTranslation } from "react-i18next";
import { localeFromLanguage } from "@/lib/i18n/locale";
import { formatRelativeDate } from "@/lib/time";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

interface RecordedAtCellProps {
  recordedAt?: string | null;
  sortRecordedAt?: string | null;
}

/** Render a score update date using the shared rating-detail display rules. */
export function RecordedAtCell({ recordedAt, sortRecordedAt }: RecordedAtCellProps) {
  const { t, i18n } = useTranslation();
  const dateLocale = localeFromLanguage(i18n.language);

  if (recordedAt) {
    return (
      <TooltipProvider delayDuration={200}>
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="cursor-default">
              {formatRelativeDate(recordedAt, "--", t)}
              <span className="ml-0.5 text-accent/70 leading-none">●</span>
            </span>
          </TooltipTrigger>
          <TooltipContent side="top" className="text-label">
            {new Date(recordedAt).toLocaleDateString(dateLocale)}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  if (sortRecordedAt) {
    return (
      <TooltipProvider delayDuration={200}>
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="cursor-default text-muted-foreground row-muted">
              --
              <span className="ml-0.5 text-accent/70 leading-none">●</span>
            </span>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-64 text-label">
            {t("ranking.detail.preSyncRecordTooltip")}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return <span className="text-muted-foreground row-muted">--</span>;
}
