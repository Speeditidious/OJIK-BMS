const INTERACTIVE_ROW_TARGET_SELECTOR =
  'a, button, [role="button"], input, select, textarea, label, [data-rating-cell]';

/**
 * Return whether a click target should toggle an expandable fumen row.
 *
 * Blank cells and ordinary text toggle the row. Interactive descendants keep
 * their own behavior. Do not treat library-owned state attributes as
 * interactive: tooltip primitives add them to otherwise ordinary text.
 * `[data-rating-cell]` opts the rating-value cell out of row-toggle even for
 * non-button descendants inside it (defense in depth alongside the button's
 * own `stopPropagation`).
 */
export function shouldToggleFumenRow(target) {
  return !target.closest(INTERACTIVE_ROW_TARGET_SELECTOR);
}
