import test from "node:test";
import assert from "node:assert/strict";

import { selectAnnouncementBody } from "./update-announcement-core.js";

const announcement = {
  body_markdown: "Korean notes",
  body_markdown_en: "English notes",
  body_markdown_ja: "Japanese notes",
};

test("selectAnnouncementBody returns English body for English language", () => {
  assert.equal(selectAnnouncementBody(announcement, "en"), "English notes");
});

test("selectAnnouncementBody returns Japanese body for Japanese language", () => {
  assert.equal(selectAnnouncementBody(announcement, "ja"), "Japanese notes");
});

test("selectAnnouncementBody falls back to default body when localized body is blank", () => {
  assert.equal(
    selectAnnouncementBody({ ...announcement, body_markdown_en: "   " }, "en"),
    "Korean notes",
  );
});
