const RATE_PRECISION = 2;
const RATE_SCALE = 10 ** RATE_PRECISION;
const RATE_EPSILON = 1e-9;

function formatRateValue(value: number): string {
  const scaled = Math.floor((value + RATE_EPSILON) * RATE_SCALE);
  const whole = Math.trunc(scaled / RATE_SCALE);
  const fraction = Math.abs(scaled % RATE_SCALE).toString().padStart(RATE_PRECISION, "0");
  return `${whole}.${fraction}`;
}

export function formatRatePercent(rate: number): string {
  return `${formatRateValue(rate)}%`;
}

export function formatRateDelta(rateDelta: number): string {
  const direction = rateDelta > 0 ? "▲" : "▼";
  return `${direction}${formatRateValue(Math.abs(rateDelta))}`;
}
