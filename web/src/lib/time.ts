export type Translate = (key: string, options?: Record<string, unknown>) => string;

const fallbackTranslations: Record<string, string> = {
  "format.timeAgo.none": "--",
  "format.timeAgo.justNow": "Just now",
  "format.timeAgo.oneMinute": "1 minute ago",
  "format.timeAgo.minutes": "{{count}} minutes ago",
  "format.timeAgo.oneHour": "1 hour ago",
  "format.timeAgo.hours": "{{count}} hours ago",
  "format.timeAgo.today": "Today",
  "format.timeAgo.yesterday": "Yesterday",
  "format.timeAgo.day": "1 day ago",
  "format.timeAgo.days": "{{count}} days ago",
  "format.timeAgo.week": "1 week ago",
  "format.timeAgo.weeks": "{{count}} weeks ago",
  "format.timeAgo.month": "1 month ago",
  "format.timeAgo.months": "{{count}} months ago",
  "format.timeAgo.year": "1 year ago",
  "format.timeAgo.years": "{{count}} years ago",
  "format.date.join": "{{year}}-{{month}}-{{day}}",
  "format.duration.zeroHours": "0 hours",
  "format.duration.hour": "1 hour",
  "format.duration.hours": "{{count}} hours",
  "format.duration.minute": "1 minute",
  "format.duration.minutes": "{{count}} minutes",
  "format.duration.hourMinute": "1 hour 1 minute",
  "format.duration.hourMinutes": "1 hour {{minutes}} minutes",
  "format.duration.hoursMinute": "{{hours}} hours 1 minute",
  "format.duration.hoursMinutes": "{{hours}} hours {{minutes}} minutes",
};

function fallbackT(key: string, options: Record<string, unknown> = {}): string {
  const template = fallbackTranslations[key] ?? key;
  return template.replace(/\{\{(\w+)\}\}/g, (_, name: string) => String(options[name] ?? ""));
}

function translate(t: Translate | undefined, key: string, options?: Record<string, unknown>): string {
  return (t ?? fallbackT)(key, options);
}

export function formatRelativeDate(
  isoString: string | null | undefined,
  fallback = "--",
  t?: Translate,
): string {
  if (!isoString) return fallback;
  const now = new Date();
  const date = new Date(isoString);
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const dateStart = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const diffDays = Math.round((todayStart.getTime() - dateStart.getTime()) / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return translate(t, "format.timeAgo.today");
  if (diffDays === 1) return translate(t, "format.timeAgo.yesterday");
  if (diffDays < 7) return translate(t, "format.timeAgo.days", { count: diffDays });
  if (diffDays < 30) {
    const weeks = Math.floor(diffDays / 7);
    return translate(t, weeks === 1 ? "format.timeAgo.week" : "format.timeAgo.weeks", { count: weeks });
  }
  if (diffDays < 365) {
    const months = Math.floor(diffDays / 30);
    return translate(t, months === 1 ? "format.timeAgo.month" : "format.timeAgo.months", { count: months });
  }
  const years = Math.floor(diffDays / 365);
  return translate(t, years === 1 ? "format.timeAgo.year" : "format.timeAgo.years", { count: years });
}

export function timeAgo(isoString: string | null | undefined, t?: Translate): string {
  if (!isoString) return translate(t, "format.timeAgo.none");
  const diff = Date.now() - new Date(isoString).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 45) return translate(t, "format.timeAgo.justNow");
  if (seconds < 90) return translate(t, "format.timeAgo.oneMinute");
  const minutes = Math.floor(seconds / 60);
  if (minutes < 45) return translate(t, "format.timeAgo.minutes", { count: minutes });
  if (minutes < 90) return translate(t, "format.timeAgo.oneHour");
  const hours = Math.floor(minutes / 60);
  if (hours < 22) return translate(t, "format.timeAgo.hours", { count: hours });
  if (hours < 36) return translate(t, "format.timeAgo.yesterday");
  const days = Math.floor(hours / 24);
  return translate(t, days === 1 ? "format.timeAgo.day" : "format.timeAgo.days", { count: days });
}

export function formatJoinDate(isoString: string, t?: Translate): string {
  const date = new Date(isoString);
  return translate(t, "format.date.join", {
    year: date.getFullYear(),
    month: date.getMonth() + 1,
    day: date.getDate(),
  });
}

export function formatDuration(seconds: number, t?: Translate): string {
  if (seconds <= 0) return translate(t, "format.duration.zeroHours");
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0 && minutes > 0) {
    if (hours === 1 && minutes === 1) return translate(t, "format.duration.hourMinute");
    if (hours === 1) return translate(t, "format.duration.hourMinutes", { minutes });
    if (minutes === 1) return translate(t, "format.duration.hoursMinute", { hours });
    return translate(t, "format.duration.hoursMinutes", { hours, minutes });
  }
  if (hours > 0) {
    return translate(t, hours === 1 ? "format.duration.hour" : "format.duration.hours", { count: hours });
  }
  return translate(t, minutes === 1 ? "format.duration.minute" : "format.duration.minutes", { count: minutes });
}
