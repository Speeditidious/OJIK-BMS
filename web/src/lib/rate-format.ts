const RATE_PRECISION = 2;

export function formatRatePercent(rate: number): string {
  return `${rate.toFixed(RATE_PRECISION)}%`;
}

export function formatRateDelta(rateDelta: number): string {
  const direction = rateDelta > 0 ? "▲" : "▼";
  return `${direction}${Math.abs(rateDelta).toFixed(RATE_PRECISION)}`;
}
