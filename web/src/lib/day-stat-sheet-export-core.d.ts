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

export function getSectionSplitGroups(sectionIds: string[]): string[][];

export function getHeightSplitRanges(
  blocks: ExportBlock[],
  options: { maxHeight: number; preserveBlocks: boolean },
): ExportRange[];
