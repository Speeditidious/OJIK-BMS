import assert from "node:assert/strict";
import test from "node:test";

import { preprocessMarkdownMentions } from "./markdown-content-core.mjs";

test("preprocessMarkdownMentions links issue references in announcement markdown", () => {
  const markdown = "관련 이슈는 #123 입니다.";

  assert.equal(
    preprocessMarkdownMentions(markdown),
    "관련 이슈는 [#123](/issues/123) 입니다.",
  );
});

test("preprocessMarkdownMentions leaves issue references inside code untouched", () => {
  const markdown = "Use `#123` here.\n\n```\n#456\n```";

  assert.equal(preprocessMarkdownMentions(markdown), markdown);
});

test("preprocessMarkdownMentions links unresolved Korean usernames", () => {
  assert.equal(
    preprocessMarkdownMentions("@레드볼 확인 부탁드립니다."),
    "[@레드볼](/u/레드볼) 확인 부탁드립니다.",
  );
});

test("preprocessMarkdownMentions links unresolved Japanese usernames", () => {
  assert.equal(
    preprocessMarkdownMentions("@レッドボール 確認お願いします。"),
    "[@レッドボール](/u/レッドボール) 確認お願いします。",
  );
});

test("preprocessMarkdownMentions links resolved Korean usernames to dashboards", () => {
  assert.equal(
    preprocessMarkdownMentions("@레드볼 확인 부탁드립니다.", [
      { source_text: "@레드볼", user: { id: "user-1", username: "레드볼" } },
    ]),
    "[@레드볼](/users/user-1/dashboard) 확인 부탁드립니다.",
  );
});

test("preprocessMarkdownMentions links resolved Japanese usernames to dashboards", () => {
  assert.equal(
    preprocessMarkdownMentions("@レッドボール 確認お願いします。", [
      { source_text: "@レッドボール", user: { id: "user-1", username: "レッドボール" } },
    ]),
    "[@レッドボール](/users/user-1/dashboard) 確認お願いします。",
  );
});
