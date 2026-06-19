export function getDashboardRankingTable(
  params: URLSearchParams,
  fallbackSlug: string | null | undefined,
): string | null;

export function mergeDashboardParams(
  currentParams: string | URLSearchParams,
  updates: Record<string, string | null>,
): URLSearchParams;

export function buildDashboardUrl(
  pathname: string,
  currentParams: string | URLSearchParams,
  updates: Record<string, string | null>,
): string;
