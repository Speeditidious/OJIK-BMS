import assert from "node:assert/strict";
import test from "node:test";

import { getAnnouncementEditorState } from "./announcement-editor-state.mjs";

test("create mode can load drafts and exposes draft plus publish actions", () => {
  const state = getAnnouncementEditorState({ isEditMode: false });

  assert.equal(state.showDraftLoader, true);
  assert.deepEqual(state.actions, ["saveDraft", "publish"]);
});

test("edit mode updates only and does not expose draft or publish actions", () => {
  const state = getAnnouncementEditorState({ isEditMode: true });

  assert.equal(state.showDraftLoader, false);
  assert.deepEqual(state.actions, ["update"]);
});
