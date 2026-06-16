import type { CategoryMeta } from "@/lib/weekly-types";

const KEY_PREFIX = "ojik:lastWeekly:";

export interface WeeklyPosition {
  category: string;
  bracket: string;
}

function keyFor(userId: string): string {
  return `${KEY_PREFIX}${userId}`;
}

export function saveLastWeekly(userId: string | null | undefined, pos: WeeklyPosition): void {
  if (typeof window === "undefined" || !userId) return;
  try {
    window.localStorage.setItem(keyFor(userId), JSON.stringify(pos));
  } catch {
    // ignore quota/private-mode errors
  }
}

export function readLastWeekly(userId: string | null | undefined): WeeklyPosition | null {
  if (typeof window === "undefined" || !userId) return null;
  try {
    const raw = window.localStorage.getItem(keyFor(userId));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.category === "string" && typeof parsed.bracket === "string") {
      return parsed;
    }
  } catch {
    // ignore
  }
  return null;
}

export function resolvePosition(
  categories: CategoryMeta[],
  requested: WeeklyPosition | null,
): WeeklyPosition | null {
  if (categories.length === 0) return null;
  const first = (): WeeklyPosition => ({
    category: categories[0].key,
    bracket: categories[0].brackets[0]?.key ?? "",
  });

  if (!requested) return first();

  const cat = categories.find((c) => c.key === requested.category);
  if (!cat) return first();

  const hasBracket = cat.brackets.some((b) => b.key === requested.bracket);
  if (hasBracket) return requested;

  return { category: cat.key, bracket: cat.brackets[0]?.key ?? "" };
}
