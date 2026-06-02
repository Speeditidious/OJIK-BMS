import assert from "node:assert/strict";
import test from "node:test";

import { getMentionAutocompleteTrigger } from "./mention-autocomplete-core.mjs";

test("getMentionAutocompleteTrigger detects a trailing issue reference number", () => {
  assert.deepEqual(getMentionAutocompleteTrigger("공지 본문 #123"), {
    type: "issue",
    query: "123",
  });
});

test("getMentionAutocompleteTrigger detects an empty trailing issue reference", () => {
  assert.deepEqual(getMentionAutocompleteTrigger("관련 이슈 #"), {
    type: "issue",
    query: "",
  });
});

test("getMentionAutocompleteTrigger ignores non-trailing issue references", () => {
  assert.equal(getMentionAutocompleteTrigger("#123 확인 후 계속 작성"), null);
});

test("getMentionAutocompleteTrigger detects a trailing Korean username", () => {
  assert.deepEqual(getMentionAutocompleteTrigger("답글 @레드"), {
    type: "user",
    query: "레드",
  });
});

test("getMentionAutocompleteTrigger detects a trailing Japanese username", () => {
  assert.deepEqual(getMentionAutocompleteTrigger("返信 @レッド"), {
    type: "user",
    query: "レッド",
  });
});
