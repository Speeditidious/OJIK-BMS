/**
 * Returns the active trailing autocomplete trigger for markdown editors.
 */
export function getMentionAutocompleteTrigger(text) {
  const atMatch = text.match(/(?:^|[\s\n])@([A-Za-z0-9_]*)$/);
  if (atMatch) return { type: "user", query: atMatch[1] };

  const hashMatch = text.match(/(?:^|[\s\n])#([0-9]*)$/);
  if (hashMatch) return { type: "issue", query: hashMatch[1] };

  return null;
}
