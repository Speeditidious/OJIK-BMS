"use client";

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface SourceClientBadgeProps {
  sourceClient?: string | null;
  sourceClientDetail?: Record<string, string | null> | null;
  fallbackClientTypes?: string[] | null;
  className?: string;
}

function fallbackLabel(clientTypes?: string[] | null): string | null {
  const unique = Array.from(new Set((clientTypes ?? []).filter(Boolean)));
  if (unique.length === 0) return null;
  if (unique.length > 1) return "MIX";
  if (unique[0] === "lr2") return "LR";
  if (unique[0] === "beatoraja") return "BR";
  return unique[0]?.toUpperCase() ?? null;
}

export function SourceClientBadge({
  sourceClient,
  sourceClientDetail,
  fallbackClientTypes,
  className,
}: SourceClientBadgeProps) {
  const label = sourceClient ?? fallbackLabel(fallbackClientTypes);
  if (!label) return null;

  const isMix = label === "MIX";
  const badge = (
    <span className={cn("text-label", isMix && "cursor-help", className)}>
      {label}
      {isMix && <span className="ml-0.5 text-accent/70 leading-none">●</span>}
    </span>
  );

  if (label !== "MIX" || !sourceClientDetail) return badge;

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>{badge}</TooltipTrigger>
        <TooltipContent side="left" className="text-label">
          <div className="space-y-0.5">
            {sourceClientDetail.clear_type && (
              <div>클리어: {sourceClientDetail.clear_type}</div>
            )}
            {sourceClientDetail.exscore && (
              <div>점수: {sourceClientDetail.exscore}</div>
            )}
            {sourceClientDetail.min_bp && (
              <div>BP: {sourceClientDetail.min_bp}</div>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
