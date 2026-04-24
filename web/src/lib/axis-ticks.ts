/** Pick a "nice" step size for a data range. */
export function niceStep(range: number, target: number): number {
  if (range === 0 || target <= 0) return 1;
  const rough = range / target;
  const exp = Math.floor(Math.log10(rough));
  const factor = rough / Math.pow(10, exp);
  const nice = factor < 1.5 ? 1 : factor < 3.5 ? 2 : factor < 7.5 ? 5 : 10;
  return nice * Math.pow(10, exp);
}

/**
 * Compute evenly-spaced "nice" Y-axis ticks within [min, max].
 * Step is rounded to a base-10 nice number (1, 2, 5 × 10^k).
 * Returned ticks satisfy: min ≤ tick ≤ max for every entry.
 *
 * Returns `{ ticks, step }`. When `min === max`, returns `{ ticks: [], step: 0 }`.
 */
export function niceTicks(
  min: number,
  max: number,
  target = 8,
): { ticks: number[]; step: number } {
  const range = max - min;
  if (range === 0) return { ticks: [], step: 0 };

  const step = niceStep(range, target);
  const start = Math.ceil((min - step * 1e-9) / step) * step;
  const result: number[] = [];
  for (let i = 0; ; i++) {
    const tick = start + i * step;
    if (tick > max + step * 1e-9) break;
    result.push(tick);
  }
  return { ticks: result, step };
}

/** Number of decimal places needed to represent a given step without rounding artifacts. */
export function decimalsForStep(step: number): number {
  if (step === 0 || !isFinite(step)) return 0;
  if (step >= 1) return 0;
  return Math.max(0, -Math.floor(Math.log10(step) - 1e-9));
}
