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
