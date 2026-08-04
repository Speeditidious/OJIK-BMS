/**
 * Render a goal timestamp as a local-timezone `YYYY.MM.DD` string.
 * Returns an empty string when the value is missing or unparseable, so
 * callers can render it unconditionally.
 */
export function formatGoalDate(isoString) {
  if (!isoString) return "";
  const parsed = new Date(isoString);
  if (Number.isNaN(parsed.getTime())) return "";
  const year = parsed.getFullYear();
  const month = String(parsed.getMonth() + 1).padStart(2, "0");
  const day = String(parsed.getDate()).padStart(2, "0");
  return `${year}.${month}.${day}`;
}
