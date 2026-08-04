// Pure month-grid arithmetic shared by every calendar popup in the app.
// All dates are "YYYY-MM-DD" strings so they compare lexicographically;
// `month` is always 1-based.

export function pad2(n) {
  return String(n).padStart(2, "0");
}

export function toDateString(year, month, day) {
  return `${year}-${pad2(month)}-${pad2(day)}`;
}

/** Move `delta` months from (year, month), wrapping across year boundaries. */
export function shiftMonth(year, month, delta) {
  const zeroBased = (year * 12 + (month - 1)) + delta;
  return { year: Math.floor(zeroBased / 12), month: (zeroBased % 12) + 1 };
}

function daysInMonth(year, month) {
  return new Date(year, month, 0).getDate();
}

/**
 * Six full weeks of day cells (42 entries) covering the given month, padded
 * with the neighbouring months' days. Fixing the row count keeps the popup
 * from resizing as the user navigates.
 */
export function buildMonthCells(year, month) {
  const cells = [];
  const firstDayOfWeek = new Date(year, month - 1, 1).getDay(); // 0 = Sunday
  const total = daysInMonth(year, month);
  const prev = shiftMonth(year, month, -1);
  const prevTotal = daysInMonth(prev.year, prev.month);

  for (let i = firstDayOfWeek - 1; i >= 0; i--) {
    const day = prevTotal - i;
    cells.push({
      dateStr: toDateString(prev.year, prev.month, day),
      day,
      currentMonth: false,
    });
  }
  for (let day = 1; day <= total; day++) {
    cells.push({ dateStr: toDateString(year, month, day), day, currentMonth: true });
  }
  const next = shiftMonth(year, month, 1);
  for (let day = 1; cells.length < 42; day++) {
    cells.push({
      dateStr: toDateString(next.year, next.month, day),
      day,
      currentMonth: false,
    });
  }
  return cells;
}

/** The inclusive first..last day of a month, for range-scoped data fetches. */
export function getMonthRange(year, month) {
  return {
    from: toDateString(year, month, 1),
    to: toDateString(year, month, daysInMonth(year, month)),
  };
}

/** Whether a month starts strictly after `dateStr` — used to disable forward nav. */
export function isMonthAfter(year, month, dateStr) {
  return toDateString(year, month, 1) > dateStr;
}

/**
 * The range a picker would commit if the user clicked `hover` right now.
 *
 * Returns null unless exactly the start bound is set — before the first click
 * there is nothing to extend from, and after the second there is nothing left
 * to preview.
 */
export function previewRange(from, to, hover) {
  if (!from || to || !hover) return null;
  return hover < from ? { from: hover, to: from } : { from, to: hover };
}
