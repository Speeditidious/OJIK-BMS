/**
 * Formats a date as a relative time string using Intl.RelativeTimeFormat.
 * Supports ko, en, ja — all handled natively by Intl.
 * Falls back to absolute date for dates older than 30 days.
 */
export function formatRelativeTime(dateStr: string, locale: string): string {
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return dateStr;

  const diffMs = date.getTime() - Date.now();
  const diffSec = diffMs / 1000;
  const absSec = Math.abs(diffSec);

  let value: number;
  let unit: Intl.RelativeTimeFormatUnit;

  if (absSec < 60) {
    value = Math.round(diffSec);
    unit = "seconds";
  } else if (absSec < 3600) {
    value = Math.round(diffSec / 60);
    unit = "minutes";
  } else if (absSec < 86400) {
    value = Math.round(diffSec / 3600);
    unit = "hours";
  } else if (absSec < 86400 * 30) {
    value = Math.round(diffSec / 86400);
    unit = "days";
  } else {
    // Older than 30 days: absolute date
    return date.toLocaleDateString(locale, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }

  try {
    return new Intl.RelativeTimeFormat(locale, { numeric: "auto" }).format(value, unit);
  } catch {
    return date.toLocaleString(locale);
  }
}
