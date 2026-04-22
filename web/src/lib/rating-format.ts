/** Supported rating metric kinds. */
export type RatingMetricKind = "exp" | "rating" | "bmsforce";

/**
 * Format a large number compactly for Y-axis ticks.
 * - NaN / Infinity → "-"
 * - 0 → "0"
 * - |n| < 1000 → integer string
 * - |n| < 1_000_000 → "XXk" (1 decimal, trailing zero removed)
 * - |n| < 1_000_000_000 → "Xm"
 * - otherwise → "Xb"
 */
export function formatCompactNumber(n: number): string {
  if (!Number.isFinite(n)) return "-";
  if (n === 0) return "0";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (abs < 1000) return `${sign}${Math.round(abs)}`;
  if (abs < 1_000_000) {
    const k = abs / 1000;
    const formatted = k % 1 === 0 ? `${Math.round(k)}k` : `${k.toFixed(1)}k`;
    return `${sign}${formatted}`;
  }
  if (abs < 1_000_000_000) {
    const m = abs / 1_000_000;
    const formatted = m % 1 === 0 ? `${Math.round(m)}m` : `${m.toFixed(1)}m`;
    return `${sign}${formatted}`;
  }
  const b = abs / 1_000_000_000;
  const formatted = b % 1 === 0 ? `${Math.round(b)}b` : `${b.toFixed(1)}b`;
  return `${sign}${formatted}`;
}

/**
 * Format a rating metric value:
 * - exp/rating → integer, locale-formatted
 * - bmsforce   → 3 decimal places
 */
export function formatRatingMetric(kind: RatingMetricKind, value: number): string {
  if (!Number.isFinite(value)) return "-";
  if (kind === "bmsforce") return value.toFixed(3);
  return Math.round(value).toLocaleString();
}

/**
 * Format a rating delta with sign prefix.
 * Returns "-" if delta is effectively zero.
 */
export function formatRatingDelta(kind: RatingMetricKind, delta: number): string {
  if (!Number.isFinite(delta)) return "-";
  const threshold = kind === "bmsforce" ? 5e-4 : 0.5;
  if (Math.abs(delta) < threshold) return "-";
  const magnitude = formatRatingMetric(kind, Math.abs(delta));
  return delta > 0 ? `+${magnitude}` : `-${magnitude}`;
}
