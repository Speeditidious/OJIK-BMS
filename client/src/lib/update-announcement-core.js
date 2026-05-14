export function selectAnnouncementBody(announcement, language) {
  const localized =
    language === "en"
      ? announcement.body_markdown_en
      : language === "ja"
        ? announcement.body_markdown_ja
        : null;
  return localized && localized.trim() ? localized : announcement.body_markdown;
}
