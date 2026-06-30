export interface ExportBlock {
  id: string;
  top: number;
  bottom: number;
  keepWithNext?: boolean;
}

export interface ExportRange {
  top: number;
  bottom: number;
}

export interface RatingChangeState {
  hasRatingChange?: boolean;
  hasBmsforceChange?: boolean;
}

export function getSectionSplitGroups(sectionIds: string[]): string[][];

export function getHeightSplitRanges(
  blocks: ExportBlock[],
  options: { maxHeight: number; preserveBlocks: boolean },
): ExportRange[];

export function shouldShowRatingChangeTable(change: {
  expDelta?: number | null;
  ratingDelta?: number | null;
  bmsforceDelta?: number | null;
}): boolean;

export function shouldShowRatingChangeArea(args: {
  selectedTableSlugs: string[];
  tableChangesBySlug: Record<string, RatingChangeState | undefined>;
}): boolean;
