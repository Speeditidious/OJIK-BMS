/** BPM 표시: "150" 또는 "120~180 (150)" — min==max이면 단일 값 */
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

/** Notes 표시 */
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

/** Length 표시: ms → "2:30" または "1:05:30" */
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
