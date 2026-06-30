/**
 * @typedef {{ id: string, top: number, bottom: number, keepWithNext?: boolean }} ExportBlock
 * @typedef {{ top: number, bottom: number }} ExportRange
 * @typedef {{ hasRatingChange?: boolean, hasBmsforceChange?: boolean }} RatingChangeState
 */

const CHANGE_EPSILON = 1e-9;

/**
 * Builds the two section-based export groups.
 *
 * @param {string[]} sectionIds
 * @returns {string[][]}
 */
export function getSectionSplitGroups(sectionIds) {
  const base = sectionIds.filter((id) => id !== "rating" && id !== "record");
  const hasRating = sectionIds.includes("rating");
  const hasRecord = sectionIds.includes("record");

  if (!hasRating || !hasRecord) return [sectionIds];

  return [
    [...base, "rating"],
    [...base, "record"],
  ];
}

/**
 * Converts measured blocks into vertical export ranges.
 *
 * @param {ExportBlock[]} blocks
 * @param {{ maxHeight: number, preserveBlocks: boolean }} options
 * @returns {ExportRange[]}
 */
export function getHeightSplitRanges(blocks, options) {
  const maxHeight = Math.max(1, Math.floor(options.maxHeight));
  if (blocks.length === 0) return [];

  const sheetTop = Math.min(...blocks.map((block) => block.top));
  const sheetBottom = Math.max(...blocks.map((block) => block.bottom));
  if (!options.preserveBlocks) {
    const ranges = [];
    for (let top = sheetTop; top < sheetBottom; top += maxHeight) {
      ranges.push({ top, bottom: Math.min(top + maxHeight, sheetBottom) });
    }
    return ranges;
  }

  /** @type {ExportRange[]} */
  const unitsInDomOrder = [];
  for (let i = 0; i < blocks.length; i += 1) {
    const block = blocks[i];
    const next = blocks[i + 1];
    if (block.keepWithNext && next) {
      unitsInDomOrder.push({ top: block.top, bottom: next.bottom });
      i += 1;
    } else {
      unitsInDomOrder.push({ top: block.top, bottom: block.bottom });
    }
  }
  const units = unitsInDomOrder.sort((a, b) => a.top - b.top || a.bottom - b.bottom);

  /** @type {ExportRange[]} */
  const ranges = [];
  let index = 0;
  while (index < units.length) {
    const currentTop = units[index].top;
    let currentBottom = units[index].bottom;
    let nextIndex = index + 1;

    while (nextIndex < units.length) {
      const next = units[nextIndex];
      const overlapsCurrentPage = next.top < currentBottom;
      const exceedsHeight = next.bottom - currentTop > maxHeight;
      if (exceedsHeight && !overlapsCurrentPage) break;
      currentBottom = Math.max(currentBottom, next.bottom);
      nextIndex += 1;
    }

    ranges.push({ top: currentTop, bottom: currentBottom });
    index = nextIndex;
  }
  return ranges;
}

/**
 * Returns true when a table has a visible rating-related change.
 * EXP-only movement is intentionally ignored for the day-stat rating section.
 *
 * @param {{ expDelta?: number | null, ratingDelta?: number | null, bmsforceDelta?: number | null }} change
 * @returns {boolean}
 */
export function shouldShowRatingChangeTable(change) {
  return (
    Math.abs(change.ratingDelta ?? 0) > CHANGE_EPSILON ||
    Math.abs(change.bmsforceDelta ?? 0) > CHANGE_EPSILON
  );
}

/**
 * Keeps the rating area visible while data is loading, then hides it when every
 * selected table has no rating-related movement.
 *
 * @param {{ selectedTableSlugs: string[], tableChangesBySlug: Record<string, RatingChangeState | undefined> }} args
 * @returns {boolean}
 */
export function shouldShowRatingChangeArea({ selectedTableSlugs, tableChangesBySlug }) {
  if (selectedTableSlugs.length === 0) return false;

  return selectedTableSlugs.some((slug) => {
    const state = tableChangesBySlug[slug];
    if (!state) return true;
    return Boolean(state.hasRatingChange || state.hasBmsforceChange);
  });
}
