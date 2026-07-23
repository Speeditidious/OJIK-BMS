import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useFumenDetail } from "@/hooks/use-fumen-detail";
import type { TableLevelRef } from "@/components/common/TableLevelBadges";
import type { DifficultyTable } from "@/types";

/**
 * All difficulty tables a chart belongs to, in the same shape/source as the
 * song detail page's "belonging tables" section (`SongDetailPage`'s
 * `tableEntries` + `tableMetaMap`) — reused here for goal cards so a chart
 * goal shows the chart's real table memberships, not just the table it was
 * targeted through.
 */
export function useFumenTableLevels(sha256: string | null, md5: string | null): TableLevelRef[] {
  const hash = sha256 || md5 || null;
  const { data: fumen } = useFumenDetail(hash);
  const { data: allTables = [] } = useQuery<DifficultyTable[]>({
    queryKey: ["tables"],
    queryFn: () => api.get<DifficultyTable[]>("/tables/"),
    staleTime: 5 * 60 * 1000,
    enabled: !!hash,
  });

  if (!fumen?.table_entries?.length || allTables.length === 0) return [];
  const tableById = new Map(allTables.map((table) => [table.id, table]));
  return fumen.table_entries
    .map((entry) => {
      const table = tableById.get(entry.table_id);
      if (!table?.slug) return null;
      return { symbol: table.symbol ?? "", slug: table.slug, level: entry.level };
    })
    .filter((entry): entry is TableLevelRef => entry !== null);
}
