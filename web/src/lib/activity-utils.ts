export function buildCountMap(items?: Array<{ date: string; count: number }>): Record<string, number> {
  const map: Record<string, number> = {};
  for (const item of items ?? []) {
    map[item.date] = item.count;
  }
  return map;
}

export function mergeActivityWithRating<T extends { date: string; rating_updates?: number }>(
  data: T[],
  ratingUpdates: Array<{ date: string; count: number }> | undefined,
): T[] {
  const ratingMap = buildCountMap(ratingUpdates);
  return data.map((item) => ({
    ...item,
    rating_updates: ratingMap[item.date] ?? 0,
  }));
}
