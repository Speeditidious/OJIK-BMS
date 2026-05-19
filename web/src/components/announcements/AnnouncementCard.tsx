"use client";

import { useTranslation } from "react-i18next";
import { MarkdownContent } from "@/components/common/MarkdownContent";
import type { Announcement } from "@/types";

interface AnnouncementCardProps {
  announcement: Announcement;
  /** When true, truncates body preview to 3 lines (for home page preview) */
  preview?: boolean;
}

/**
 * Maps a tag color token to a CSS variable pair: [border color, badge background, badge text].
 * The `color` field from the server is a design system token name (e.g. "primary", "accent").
 * Falls back to primary when null or unrecognized.
 */
function resolveTagColor(color: string | null): {
  borderVar: string;
  badgeBg: string;
  badgeText: string;
} {
  const token = color ?? "primary";
  const map: Record<string, { borderVar: string; badgeBg: string; badgeText: string }> = {
    primary: {
      borderVar: "hsl(var(--primary))",
      badgeBg: "hsl(var(--primary) / 0.15)",
      badgeText: "hsl(var(--primary))",
    },
    accent: {
      borderVar: "hsl(var(--accent))",
      badgeBg: "hsl(var(--accent) / 0.15)",
      badgeText: "hsl(var(--accent))",
    },
    warning: {
      borderVar: "hsl(var(--warning))",
      badgeBg: "hsl(var(--warning) / 0.15)",
      badgeText: "hsl(var(--warning))",
    },
    destructive: {
      borderVar: "hsl(var(--destructive))",
      badgeBg: "hsl(var(--destructive) / 0.15)",
      badgeText: "hsl(var(--destructive))",
    },
  };
  return map[token] ?? map.primary;
}

export function AnnouncementCard({ announcement, preview = false }: AnnouncementCardProps) {
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

  const { borderVar, badgeBg, badgeText } = resolveTagColor(announcement.tag.color);

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString(lang, { year: "numeric", month: "numeric", day: "numeric" });

  const createdDate = formatDate(announcement.created_at);

  const createdDay = new Date(announcement.created_at).toDateString();
  const updatedDay = new Date(announcement.updated_at).toDateString();
  const updatedDate = createdDay !== updatedDay ? formatDate(announcement.updated_at) : null;

  return (
    <article
      className="flex overflow-hidden rounded-lg border bg-card shadow-sm transition-colors hover:border-border/80"
      style={{ borderLeftColor: borderVar, borderLeftWidth: "4px" }}
    >
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
