const INTERACTIVE_ROW_TARGET_SELECTOR =
  'a, button, [role="button"], input, select, textarea, label';

/**
 * Return whether a click target should toggle an expandable fumen row.
 *
 * Blank cells and ordinary text toggle the row. Interactive descendants keep
 * their own behavior. Do not treat library-owned state attributes as
 * interactive: tooltip primitives add them to otherwise ordinary text.
 */
export function shouldToggleFumenRow(target) {
  return !target.closest(INTERACTIVE_ROW_TARGET_SELECTOR);
}
