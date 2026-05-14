/** BPM display: "150" or "120~180 (150)" — min==max renders as a single value. */
export function formatBpm(
  main: number | null,
  min: number | null,
  max: number | null,
): string {
  if (main === null && min === null && max === null) return "-";
  if (min !== null && max !== null && min !== max) {
    const mainStr = main !== null ? ` (${main})` : "";
    return `${min}~${max}${mainStr}`;
  }
  return String(main ?? min ?? max ?? "-");
}

/** Notes display. */
export function formatNotes(
  total: number | null,
  n: number | null,
  ln: number | null,
  s: number | null,
  ls: number | null,
): { total: string; detail: string } {
  if (total === null) return { total: "-", detail: "" };
  const parts: string[] = [];
  if (n) parts.push(`N:${n}`);
  if (ln) parts.push(`LN:${ln}`);
  if (s) parts.push(`S:${s}`);
  if (ls) parts.push(`LS:${ls}`);
  return { total: String(total), detail: parts.join(" ") };
}

/** Length display: milliseconds to "2:30" or "1:05:30". */
export function formatLength(ms: number | null): string {
  if (ms === null) return "-";
  const totalSec = Math.floor(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  if (h > 0) return `${h}:${mm}:${ss}`;
  return `${m}:${ss}`;
}
