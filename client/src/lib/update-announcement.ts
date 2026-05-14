import type { LanguageCode, UpdateAnnouncement } from "../types";

export function selectAnnouncementBody(announcement: UpdateAnnouncement, language: LanguageCode): string {
  const localized =
    language === "en"
      ? announcement.body_markdown_en
      : language === "ja"
        ? announcement.body_markdown_ja
        : null;
  return localized?.trim() ? localized : announcement.body_markdown;
}
