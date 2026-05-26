"use client";

import { CircleCheck, CircleDashed, CircleDot, CircleSlash, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { IssueStatus } from "@/types";

interface StatusMeta {
  icon: LucideIcon;
  textClass: string;
  pillActiveClass: string;
}

export const ISSUE_STATUS_META: Record<IssueStatus, StatusMeta> = {
  open: {
    icon: CircleDot,
    textClass: "text-green-600 dark:text-green-400",
    pillActiveClass: "bg-green-100 dark:bg-green-950 border-green-500 text-green-700 dark:text-green-300",
  },
  work_in_progress: {
    icon: CircleDashed,
    textClass: "text-amber-600 dark:text-amber-400",
    pillActiveClass: "bg-amber-100 dark:bg-amber-950 border-amber-500 text-amber-700 dark:text-amber-300",
  },
  completed: {
    icon: CircleCheck,
    textClass: "text-purple-600 dark:text-purple-400",
    pillActiveClass: "bg-purple-100 dark:bg-purple-950 border-purple-500 text-purple-700 dark:text-purple-300",
  },
  not_planned: {
    icon: CircleSlash,
    textClass: "text-muted-foreground",
    pillActiveClass: "bg-muted border-muted-foreground/50 text-foreground",
  },
};

export const ISSUE_STATUS_ORDER: IssueStatus[] = ["open", "work_in_progress", "completed", "not_planned"];

interface IssueStatusBadgeProps {
  status: IssueStatus;
  /** Wraps the badge in a tooltip showing the status description. */
  withTooltip?: boolean;
  className?: string;
}

/**
 * Renders an issue status as an inline label with an icon. When `withTooltip` is
 * set, hovering reveals the localized `issues.statusTooltip.<status>` description.
 */
export function IssueStatusBadge({ status, withTooltip = false, className }: IssueStatusBadgeProps) {
  const { t } = useTranslation();
  const meta = ISSUE_STATUS_META[status];
  const Icon = meta.icon;

  const content = (
    <span
      className={cn(
        "inline-flex items-center gap-1 font-medium text-label",
        meta.textClass,
        className,
      )}
    >
      <Icon className="h-4 w-4" />
      {t(`issues.status.${status}`)}
    </span>
  );

  if (!withTooltip) return content;

  return (
    <Tooltip>
      <TooltipTrigger asChild>{content}</TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs text-label leading-snug">
        {t(`issues.statusTooltip.${status}`)}
      </TooltipContent>
    </Tooltip>
  );
}
