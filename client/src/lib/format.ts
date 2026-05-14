type TFn = (key: string, opts?: Record<string, unknown>) => string;

export function formatRelativeTime(
  iso: string | null | undefined,
  t: TFn,
  now: Date = new Date(),
): string {
  if (!iso) return t("client.format.none");
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return iso;
  const diffMs = now.getTime() - then.getTime();
  const sec = Math.round(diffMs / 1000);
  if (sec < 45) return t("client.format.justNow");
  if (sec < 90) return t("client.format.oneMinuteAgo");
  const min = Math.round(sec / 60);
  if (min < 45) return t("client.format.minutesAgo", { count: min });
  if (min < 90) return t("client.format.oneHourAgo");
  const hr = Math.round(min / 60);
  if (hr < 22) return t("client.format.hoursAgo", { count: hr });
  if (hr < 36) return t("client.format.yesterday");
  const day = Math.round(hr / 24);
  if (day < 26) return t("client.format.daysAgo", { count: day });
  return then.toLocaleDateString();
}

export function formatAbsolute(iso: string | null | undefined): string {
  if (!iso) return "-";
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return iso;
  return then.toLocaleString();
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function formatNumber(value: number): string {
  return value.toLocaleString();
}

export function formatLocalizedDateTime(iso: string | null | undefined, t: TFn): string {
  if (!iso) return t("client.format.absent");
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1);
  const dd = String(d.getDate());
  const hours = d.getHours();
  const minutes = d.getMinutes().toString().padStart(2, "0");
  const seconds = d.getSeconds().toString().padStart(2, "0");
  const ampm = hours >= 12 ? "PM" : "AM";
  const h = hours % 12 || 12;
  return t("client.format.dateTime", {
    year: yyyy,
    month: mm,
    day: dd,
    hour: h,
    minute: minutes,
    second: seconds,
    ampm,
  });
}
