/**
 * Returns the footer action policy for the announcement editor.
 *
 * Creation keeps the draft/publish split. Editing only updates the existing
 * published announcement and never changes publication state.
 *
 * @param {{ isEditMode: boolean }} options
 * @returns {{ showDraftLoader: boolean, actions: Array<"saveDraft" | "publish" | "update"> }}
 */
export function getAnnouncementEditorState(options) {
  if (options.isEditMode) {
    return {
      showDraftLoader: false,
      actions: ["update"],
    };
  }

  return {
    showDraftLoader: true,
    actions: ["saveDraft", "publish"],
  };
}
