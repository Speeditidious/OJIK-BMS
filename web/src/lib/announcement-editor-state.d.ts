export function getAnnouncementEditorState(options: { isEditMode: boolean }): {
  showDraftLoader: boolean;
  actions: Array<"saveDraft" | "publish" | "update">;
};
