export function getMentionAutocompleteTrigger(
  text: string,
): { type: "user" | "issue"; query: string } | null;
