"use client";

import { Pencil } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { MarkdownContent } from "@/components/common/MarkdownContent";
import { resolveTagBadgeStyle } from "@/lib/tag-color";
import type { Announcement } from "@/types";

interface AnnouncementCardProps {
  announcement: Announcement;
  /** When true, truncates body preview to 3 lines (for home page preview) */
  preview?: boolean;
  /** When true, shows the admin edit button */
  canEdit?: boolean;
  /** Called when the edit button is clicked */
  onEdit?: (announcement: Announcement) => void;
}

export function AnnouncementCard({
  announcement,
  preview = false,
  canEdit = false,
  onEdit,
}: AnnouncementCardProps) {
  const { i18n } = useTranslation();

  const lang = i18n.language;
  const tagName = lang.startsWith("en")
    ? (announcement.tag.name_en ?? announcement.tag.name)
    : lang.startsWith("ja")
      ? (announcement.tag.name_ja ?? announcement.tag.name)
      : announcement.tag.name;
  const title = lang.startsWith("en")
    ? (announcement.title_en ?? announcement.title)
    : lang.startsWith("ja")
      ? (announcement.title_ja ?? announcement.title)
      : announcement.title;
  const body =
    lang.startsWith("en")
      ? (announcement.body_en ?? announcement.body)
      : lang.startsWith("ja")
        ? (announcement.body_ja ?? announcement.body)
        : announcement.body;

  const { background: badgeBg, text: badgeText } = resolveTagBadgeStyle(announcement.tag.color);
  const borderVar = badgeText;

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString(lang, { year: "numeric", month: "numeric", day: "numeric" });

  const createdDate = formatDate(announcement.created_at);

  const createdDay = new Date(announcement.created_at).toDateString();
  const updatedDay = new Date(announcement.updated_at).toDateString();
  const updatedDate = createdDay !== updatedDay ? formatDate(announcement.updated_at) : null;

  return (
    <article
      className="relative flex overflow-hidden rounded-lg border bg-card shadow-sm transition-colors hover:border-border/80"
      style={{ borderLeftColor: borderVar, borderLeftWidth: "4px" }}
    >
      {/* Admin edit button */}
      {canEdit && (
        <Button
          variant="ghost"
          size="icon"
          className="absolute right-2 top-2 h-7 w-7 text-muted-foreground opacity-60 hover:opacity-100"
          onClick={() => onEdit?.(announcement)}
          aria-label="Edit announcement"
        >
          <Pencil className="h-3.5 w-3.5" />
        </Button>
      )}

      <div className="flex-1 p-5">
        {/* Tag badge + date */}
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span
            className="inline-flex items-center rounded-full px-2.5 py-0.5 text-caption font-semibold"
            style={{ backgroundColor: badgeBg, color: badgeText }}
          >
            {tagName}
          </span>
          <span className="text-caption text-muted-foreground">
            {createdDate}
            {updatedDate && (
              <span className="ml-1 text-muted-foreground/70">({updatedDate} 수정)</span>
            )}
          </span>
        </div>

        {/* Title */}
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>

        {/* Body */}
        <div className="mt-3">
          <MarkdownContent className="text-foreground [&_blockquote]:text-foreground">
            {body}
          </MarkdownContent>
        </div>
      </div>
    </article>
  );
}
