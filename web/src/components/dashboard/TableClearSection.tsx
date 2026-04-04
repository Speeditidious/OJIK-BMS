"use client";

import React, { memo, useState, useMemo, useCallback, useDeferredValue, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { X, Search, FileSpreadsheet } from "lucide-react";
import { useFavoriteTables } from "@/hooks/use-tables";
import { useTableClearDistribution, TableClearSong } from "@/hooks/use-analysis";
import {
  TableClearHistogram,
  ALL_CLEAR_TYPES,
} from "@/components/charts/TableClearHistogram";
import {
  CLEAR_TYPE_COLORS,
  CLEAR_TYPE_LABELS,
  LR2_CLEAR_TYPE_LABELS,
  BEATORAJA_CLEAR_TYPE_LABELS,
} from "@/components/charts/ClearDistributionChart";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { CLEAR_ROW_CLASS, ARRANGEMENT_KANJI, parseArrangement, levelSortIndex, exportToExcel } from "@/lib/fumen-table-utils";


function getClearLabel(clientType: string | null, clearType: number): string {
  if (clientType === "lr2") return LR2_CLEAR_TYPE_LABELS[clearType] ?? String(clearType);
  if (clientType === "beatoraja") return BEATORAJA_CLEAR_TYPE_LABELS[clearType] ?? String(clearType);
  return CLEAR_TYPE_LABELS[clearType] ?? String(clearType);
}

/** Format a raw level string the same way as the histogram Y-axis. */
function formatLevel(level: string, tableSymbol?: string): string {
  const label = level.startsWith("LEVEL ") ? level.slice(6) : level;
  return tableSymbol ? `${tableSymbol}${label}` : label;
}

type SortKey = "level" | "title" | "ex_score" | "rate" | "min_bp" | "clear_type" | "plays" | "option";
type SortDir = "asc" | "desc";

// BMS title sort convention:
//   0: ASCII punctuation & digits  (!"#$%...0-9)
//   1: ASCII letters               (A-Z a-z)
//   2: non-ASCII symbols           (★ ☆ etc.)
//   3: Hiragana                    (U+3040–U+309F)
//   4: Katakana                    (U+30A0–U+30FF)
//   5: CJK / Kanji                 (U+4E00–U+9FFF + Ext-A)
function charSortGroup(ch: string): number {
  const code = ch.codePointAt(0) ?? 0;
  if (code >= 0x21 && code <= 0x7E) {
    if ((code >= 0x41 && code <= 0x5A) || (code >= 0x61 && code <= 0x7A)) return 1;
    return 0;
  }
  if (code >= 0x3040 && code <= 0x309F) return 3;
  if (code >= 0x30A0 && code <= 0x30FF) return 4;
  if ((code >= 0x4E00 && code <= 0x9FFF) || (code >= 0x3400 && code <= 0x4DBF)) return 5;
  return 2;
}

function compareTitles(a: string, b: string): number {
  const aFirst = [...a][0] ?? "";
  const bFirst = [...b][0] ?? "";
  const ga = charSortGroup(aFirst);
  const gb = charSortGroup(bFirst);
  if (ga !== gb) return ga - gb;
  return a.localeCompare(b);
}

function compareSongs(a: TableClearSong, b: TableClearSong, key: SortKey, dir: SortDir, levelOrder: string[]): number {
  let result = 0;
  switch (key) {
    case "level": {
      const diff = levelSortIndex(a.level, levelOrder) - levelSortIndex(b.level, levelOrder);
      if (diff !== 0) { result = diff; break; }
      const levCmp = a.level.localeCompare(b.level);
      result = levCmp !== 0 ? levCmp : compareTitles(a.title ?? "", b.title ?? "");
      break;
    }
    case "title":
      result = compareTitles(a.title ?? "", b.title ?? "");
      break;
    case "ex_score":
      result = (a.ex_score ?? -1) - (b.ex_score ?? -1);
      break;
    case "rate":
      result = (a.rate ?? -1) - (b.rate ?? -1);
      break;
    case "min_bp":
      if (a.min_bp === null && b.min_bp === null) result = 0;
      else if (a.min_bp === null) result = 1;
      else if (b.min_bp === null) result = -1;
      else result = a.min_bp - b.min_bp;
      break;
    case "clear_type":
      result = a.clear_type - b.clear_type;
      break;
    case "plays":
      if (a.play_count === null && b.play_count === null) result = 0;
      else if (a.play_count === null) result = 1;
      else if (b.play_count === null) result = -1;
      else result = a.play_count - b.play_count;
      break;
    case "option":
      result = (parseArrangement(a.options, a.client_type) ?? "").localeCompare(
        parseArrangement(b.options, b.client_type) ?? ""
      );
      break;
  }
  return dir === "asc" ? result : -result;
}

const SortIcon = memo(function SortIcon({ colKey, sortKey, sortDir }: { colKey: SortKey; sortKey: SortKey; sortDir: SortDir }) {
  if (colKey !== sortKey) return <span className="ml-0.5 text-muted-foreground/35">⇅</span>;
  return <span className="ml-0.5">{sortDir === "asc" ? "↑" : "↓"}</span>;
});

const ROW_HEIGHT = 44;
const MAX_TABLE_HEIGHT = 420;

const SongTable = React.memo(function SongTable({ songs, levelOrder }: { songs: TableClearSong[]; levelOrder: string[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("level");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const parentRef = useRef<HTMLDivElement>(null);

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const sorted = useMemo(
    () => [...songs].sort((a, b) => compareSongs(a, b, sortKey, sortDir, levelOrder)),
    [songs, sortKey, sortDir, levelOrder]
  );

  // eslint-disable-next-line react-hooks/incompatible-library
  const rowVirtualizer = useVirtualizer({
    count: sorted.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
  });

  if (songs.length === 0) {
    return (
      <div className="flex items-center justify-center h-24 text-muted-foreground text-body">
        해당 조건의 곡이 없습니다
      </div>
    );
  }

  const virtualItems = rowVirtualizer.getVirtualItems();
  const paddingTop = virtualItems.length > 0 ? virtualItems[0].start : 0;
  const paddingBottom = virtualItems.length > 0
    ? rowVirtualizer.getTotalSize() - virtualItems[virtualItems.length - 1].end
    : 0;

  const thSort = (label: string, key: SortKey, className?: string) => (
    <th
      className={cn(
        "px-2 py-2 text-left font-medium whitespace-nowrap cursor-pointer select-none hover:text-foreground transition-colors",
        className,
      )}
      onClick={() => handleSort(key)}
    >
      {label}
      <SortIcon colKey={key} sortKey={sortKey} sortDir={sortDir} />
    </th>
  );

  return (
    <div className="rounded-md border border-border overflow-hidden">
      {/* Export toolbar — above table */}
      <div className="flex items-center justify-end px-3 py-1 border-b border-border bg-card">
        <button
          className="flex items-center gap-1.5 text-label text-muted-foreground hover:text-foreground transition-colors px-3 py-1 rounded-md border border-border/50 hover:border-border hover:bg-secondary/30"
          title="Export to Excel (.xlsx)"
          disabled={sorted.length === 0}
          onClick={() => {
            const columns = [
              { key: "level", header: "Level" },
              { key: "title", header: "Title" },
              { key: "artist", header: "Artist" },
              { key: "lamp", header: "Lamp" },
              { key: "bp", header: "BP" },
              { key: "rate", header: "Rate" },
              { key: "rank", header: "Rank" },
              { key: "score", header: "Score" },
              { key: "plays", header: "Plays" },
              { key: "option", header: "Option" },
              { key: "env", header: "Env" },
            ];
            const data = sorted.map((song) => {
              const arrangementName = parseArrangement(song.options, song.client_type);
              return {
                level: song.level,
                title: song.title ?? "",
                artist: song.artist ?? "",
                lamp: getClearLabel(song.client_type, song.clear_type),
                bp: song.min_bp ?? "",
                rate: song.rate != null ? `${song.rate.toFixed(2)}%` : "",
                rank: song.rank ?? "",
                score: song.ex_score ?? "",
                plays: song.play_count ?? "",
                option: arrangementName ? (ARRANGEMENT_KANJI[arrangementName] ?? arrangementName) : "",
                env: song.client_type ?? "",
              };
            });
            exportToExcel(data, columns, `table_clear_${new Date().toISOString().slice(0, 10)}`);
          }}
        >
          <FileSpreadsheet className="h-3.5 w-3.5" />
          Export to Excel
        </button>
      </div>

      {/* Scrollable table */}
      <div
        ref={parentRef}
        className="overflow-auto"
        style={{ maxHeight: MAX_TABLE_HEIGHT }}
      >
        <table className="w-full border-collapse" style={{ tableLayout: "fixed", minWidth: 740 }}>
          <colgroup>
            <col style={{ width: 56 }} />
            <col />
            <col style={{ width: 96 }} />
            <col style={{ width: 48 }} />
            <col style={{ width: 74 }} />
            <col style={{ width: 60 }} />
            <col style={{ width: 64 }} />
            <col style={{ width: 60 }} />
            <col style={{ width: 68 }} />
            <col style={{ width: 64 }} />
          </colgroup>

          <thead className="sticky top-0 z-10 bg-background text-label text-foreground font-medium">
            <tr className="border-b border-border">
              {thSort("Level", "level")}
              {thSort("Title", "title")}
              {thSort("Lamp", "clear_type")}
              {thSort("BP", "min_bp")}
              {thSort("Rate", "rate")}
              {thSort("Rank", "rate")}
              {thSort("Score", "ex_score")}
              {thSort("Plays", "plays")}
              {thSort("Option", "option")}
              <th className="px-2 py-2 text-left font-medium whitespace-nowrap">Env</th>
            </tr>
          </thead>

          <tbody>
            {paddingTop > 0 && (
              <tr><td colSpan={10} style={{ height: paddingTop, padding: 0, border: 0 }} /></tr>
            )}
            {virtualItems.map((virtualRow) => {
              const song = sorted[virtualRow.index];
              const arrangementName = parseArrangement(song.options, song.client_type);
              const arrangementKanji = arrangementName ? (ARRANGEMENT_KANJI[arrangementName] ?? null) : null;
              const rowClass = CLEAR_ROW_CLASS[song.clear_type] ?? "";
              return (
                <tr
                  key={song.sha256 || virtualRow.index}
                  style={{ height: ROW_HEIGHT }}
                  className={cn(
                    "border-b border-border/30",
                    rowClass || "hover:bg-secondary/50",
                  )}
                >
                  <td className="px-2 text-label">{song.level}</td>
                  <td className="px-2">
                    <div className="min-w-0 overflow-hidden">
                      {song.sha256 ? (
                        <Link
                          href={`/songs/${song.sha256}`}
                          className="text-label leading-tight truncate max-w-full hover:text-primary transition-colors block"
                        >
                          {song.title || "(제목 없음)"}
                        </Link>
                      ) : (
                        <div className="text-label leading-tight truncate max-w-full">
                          {song.title || "(제목 없음)"}
                        </div>
                      )}
                      {song.artist && (
                        <div className="text-caption text-muted-foreground row-muted truncate max-w-full">
                          {song.artist}
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="px-2">
                    <span className="text-label">
                      {getClearLabel(song.client_type, song.clear_type)}
                    </span>
                  </td>
                  <td className="px-2 text-label">
                    {song.min_bp !== null ? song.min_bp : <span className="text-muted-foreground row-muted">--</span>}
                  </td>
                  <td className="px-2 text-label">
                    {song.rate !== null ? `${song.rate.toFixed(2)}%` : <span className="text-muted-foreground row-muted">--</span>}
                  </td>
                  <td className="px-2 text-label">
                    {song.rank !== null ? song.rank : <span className="text-muted-foreground row-muted">--</span>}
                  </td>
                  <td className="px-2 text-label">
                    {song.ex_score !== null ? song.ex_score : <span className="text-muted-foreground row-muted">--</span>}
                  </td>
                  <td className="px-2 text-label">
                    {song.play_count !== null ? song.play_count : <span className="text-muted-foreground row-muted">--</span>}
                  </td>
                  <td className="px-2 text-label">
                    {arrangementKanji ? (
                      <span>{arrangementKanji}</span>
                    ) : (
                      <span className="text-muted-foreground row-muted">–</span>
                    )}
                  </td>
                  <td className="px-2">
                    {song.client_type ? (
                      <span className="text-label">
                        {song.client_type === "beatoraja" ? "BR" : song.client_type.toUpperCase()}
                      </span>
                    ) : (
                      <span className="text-muted-foreground row-muted">–</span>
                    )}
                  </td>
                </tr>
              );
            })}
            {paddingBottom > 0 && (
              <tr><td colSpan={10} style={{ height: paddingBottom, padding: 0, border: 0 }} /></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
});

// ---------------------------------------------------------------------------
// FilterPanel
// ---------------------------------------------------------------------------

interface FilterPanelProps {
  levels: string[];
  tableSymbol?: string;
  clientType?: string;
  filterLevels: Set<string>;
  filterClearTypes: Set<number>;
  filterTitle: string;
  onToggleLevel: (level: string) => void;
  onToggleClearType: (ct: number) => void;
  onTitleChange: (v: string) => void;
}

const FilterPanel = memo(function FilterPanel({
  levels,
  tableSymbol,
  clientType,
  filterLevels,
  filterClearTypes,
  filterTitle,
  onToggleLevel,
  onToggleClearType,
  onTitleChange,
}: FilterPanelProps) {
  // Which clear types are relevant for this client
  const clearTypes = useMemo(() => {
    return (ALL_CLEAR_TYPES as readonly number[]).filter((ct) => {
      if (clientType === "lr2" && (ct === 2 || ct === 6)) return false;
      return true;
    });
  }, [clientType]);

  // Pre-compute button styles for all clear types
  const clearTypeButtonStyles = useMemo(() => {
    const styles: Record<number, Record<string, React.CSSProperties>> = {};
    for (const ct of clearTypes) {
      const color = CLEAR_TYPE_COLORS[ct];
      styles[ct] = {
        active: {
          background: `${color}25`,
          color,
          borderColor: `${color}80`,
        },
        inactive: { color },
      };
    }
    return styles;
  }, [clearTypes]);

  return (
    <div className="rounded-lg border border-border/50 bg-card/50 p-3 space-y-3">
      {/* Clear type toggles */}
      <div className="flex gap-2 items-start">
        <span className="text-caption text-muted-foreground pt-[3px] w-14 shrink-0">클리어</span>
        <div className="flex flex-wrap gap-1">
          {clearTypes.map((ct) => {
            const active = filterClearTypes.has(ct);
            const label = getClearLabel(clientType ?? null, ct);
            return (
              <button
                key={ct}
                onClick={() => onToggleClearType(ct)}
                className={cn(
                  "inline-flex items-center rounded-full px-2.5 py-0.5 text-caption font-medium transition-all border",
                  active
                    ? "opacity-100"
                    : "opacity-50 hover:opacity-75 border-border/40"
                )}
                style={active ? clearTypeButtonStyles[ct]?.active : clearTypeButtonStyles[ct]?.inactive}
                title={label}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Level toggles */}
      <div className="flex gap-2 items-start">
        <span className="text-caption text-muted-foreground pt-[3px] w-14 shrink-0">레벨</span>
        <div className="flex flex-wrap gap-1 max-h-[72px] overflow-y-auto pr-1">
          {levels.map((lv) => {
            const active = filterLevels.has(lv);
            return (
              <button
                key={lv}
                onClick={() => onToggleLevel(lv)}
                className={cn(
                  "inline-flex items-center rounded px-2 py-0.5 text-caption font-medium transition-all border",
                  active
                    ? "bg-primary/15 text-primary border-primary/50"
                    : "text-muted-foreground border-border/40 hover:border-border hover:text-foreground"
                )}
              >
                {formatLevel(lv, tableSymbol)}
              </button>
            );
          })}
        </div>
      </div>

      {/* Title search */}
      <div className="flex gap-2 items-center">
        <span className="text-caption text-muted-foreground w-14 shrink-0">검색</span>
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground pointer-events-none" />
          <Input
            value={filterTitle}
            onChange={(e) => onTitleChange(e.target.value)}
            placeholder="곡명 / 아티스트"
            className="h-7 pl-6 pr-6 text-label"
          />
          {filterTitle && (
            <button
              onClick={() => onTitleChange("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
});

// ---------------------------------------------------------------------------
// TableClearSection
// ---------------------------------------------------------------------------

interface TableClearSectionProps {
  clientType?: string;
}

// URL param 키 (대시보드 기존 tab/date 파라미터와 충돌하지 않도록 접두사 d_ 사용)
const P_TBL = "d_tbl";
const P_LV  = "d_lv";
const P_CT  = "d_ct";
const P_Q   = "d_q";

export function TableClearSection({ clientType }: TableClearSectionProps) {
  const { data: favTables, isLoading: tablesLoading } = useFavoriteTables();
  const searchParams = useSearchParams();
  const router = useRouter();

  // URL에서 상태 읽기
  const selectedTableId = searchParams.get(P_TBL);
  const filterLevels = useMemo(
    () => new Set(searchParams.get(P_LV)?.split(",").filter(Boolean) ?? []),
    [searchParams]
  );
  const filterClearTypes = useMemo(
    () => new Set((searchParams.get(P_CT)?.split(",").filter(Boolean) ?? []).map(Number)),
    [searchParams]
  );
  const filterTitle = searchParams.get(P_Q) ?? "";
  const deferredTitle = useDeferredValue(filterTitle);

  // URL 업데이트 헬퍼 (기존 파라미터 보존)
  const updateParams = useCallback((updates: Record<string, string | null>) => {
    const params = new URLSearchParams(searchParams.toString());
    for (const [k, v] of Object.entries(updates)) {
      if (v) params.set(k, v); else params.delete(k);
    }
    router.replace(`/dashboard?${params.toString()}`, { scroll: false });
  }, [searchParams, router]);

  // Auto-select first table when loaded
  const effectiveTableId = selectedTableId ?? (favTables?.[0]?.id ?? null);

  const { data: dist, isLoading: distLoading } = useTableClearDistribution(effectiveTableId, clientType);

  // Ordered levels list (respects level_order if available)
  const orderedLevels = useMemo(() => {
    if (!dist) return [];
    const levelStrings = dist.levels.map((l) => l.level);
    if (dist.level_order?.length) {
      const order = dist.level_order;
      return levelStrings.sort((a, b) => order.indexOf(a) - order.indexOf(b));
    }
    return levelStrings.sort((a, b) => {
      const na = parseFloat(a), nb = parseFloat(b);
      if (!isNaN(na) && !isNaN(nb)) return na - nb;
      return a.localeCompare(b);
    });
  }, [dist]);

  const filteredSongs = useMemo(() => {
    if (!dist) return [];
    const titleLower = deferredTitle.toLowerCase();
    return dist.songs.filter((s) => {
      if (filterLevels.size > 0 && !filterLevels.has(s.level)) return false;
      if (filterClearTypes.size > 0 && !filterClearTypes.has(s.clear_type)) return false;
      if (titleLower && !s.title?.toLowerCase().includes(titleLower) && !s.artist?.toLowerCase().includes(titleLower)) return false;
      return true;
    });
  }, [dist, filterLevels, filterClearTypes, deferredTitle]);

  const isFiltered = filterLevels.size > 0 || filterClearTypes.size > 0 || deferredTitle !== "";

  // Histogram click: exclusive toggle
  const handleHistogramSelect = useCallback((level: string, clearType: number) => {
    const isExclusive =
      filterLevels.size === 1 &&
      filterLevels.has(level) &&
      filterClearTypes.size === 1 &&
      filterClearTypes.has(clearType);

    if (isExclusive) {
      updateParams({ [P_LV]: null, [P_CT]: null });
    } else {
      updateParams({ [P_LV]: level, [P_CT]: String(clearType) });
    }
  }, [filterLevels, filterClearTypes, updateParams]);

  const toggleLevel = useCallback((lv: string) => {
    const next = new Set(filterLevels);
    if (next.has(lv)) next.delete(lv); else next.add(lv);
    updateParams({ [P_LV]: next.size > 0 ? [...next].join(",") : null });
  }, [filterLevels, updateParams]);

  const toggleClearType = useCallback((ct: number) => {
    const next = new Set(filterClearTypes);
    if (next.has(ct)) next.delete(ct); else next.add(ct);
    updateParams({ [P_CT]: next.size > 0 ? [...next].join(",") : null });
  }, [filterClearTypes, updateParams]);

  const clearFilters = useCallback(() => {
    updateParams({ [P_LV]: null, [P_CT]: null, [P_Q]: null });
  }, [updateParams]);

  const handleTableSelect = useCallback((id: string) => {
    updateParams({ [P_TBL]: id, [P_LV]: null, [P_CT]: null, [P_Q]: null });
  }, [updateParams]);

  if (tablesLoading) {
    return <div className="h-48 bg-muted rounded animate-pulse" />;
  }

  if (!favTables || favTables.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground text-body">
        즐겨찾기한 난이도표가 없습니다. 난이도표 페이지에서 즐겨찾기를 추가하세요.
      </div>
    );
  }

  const tableSymbol = dist?.table_symbol || undefined;

  return (
    <div className="flex flex-col gap-4 min-h-0">
      {/* Top panel: table selector (horizontal) */}
      <div className="flex flex-row flex-wrap gap-1.5">
        {favTables.map((t) => (
          <button
            key={t.id}
            onClick={() => handleTableSelect(t.id)}
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-center transition-colors border",
              t.id === effectiveTableId
                ? "border-primary bg-primary/10 text-primary"
                : "border-border/40 text-muted-foreground hover:border-border hover:text-foreground"
            )}
            title={t.name}
          >
            <span className="text-body font-bold leading-tight">
              {t.symbol ?? t.name.slice(0, 2)}
            </span>
            <span className="text-label leading-tight">
              {t.name}
            </span>
          </button>
        ))}
      </div>

      {/* Bottom panel: histogram + filters + song table */}
      <div className="min-w-0 space-y-3">
        {distLoading ? (
          <div className="h-48 bg-muted rounded animate-pulse" />
        ) : !dist || dist.levels.length === 0 ? (
          <div className="flex items-center justify-center h-48 text-muted-foreground text-body">
            스코어 데이터가 없습니다
          </div>
        ) : (
          <>
            {/* Stacked histogram */}
            <TableClearHistogram
              levels={dist.levels}
              clientType={clientType}
              tableSymbol={tableSymbol}
              onSelect={handleHistogramSelect}
              onLevelSelect={toggleLevel}
            />

            {/* Filter panel */}
            <FilterPanel
              levels={orderedLevels}
              tableSymbol={tableSymbol}
              clientType={clientType}
              filterLevels={filterLevels}
              filterClearTypes={filterClearTypes}
              filterTitle={filterTitle}
              onToggleLevel={toggleLevel}
              onToggleClearType={toggleClearType}
              onTitleChange={(v) => updateParams({ [P_Q]: v || null })}
            />

            {/* Active filters display */}
            {isFiltered && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-label text-muted-foreground">필터:</span>
                {[...filterLevels].map((lv) => (
                  <Badge key={lv} variant="secondary" className="text-label gap-1 h-5">
                    {formatLevel(lv, tableSymbol)}
                    <button onClick={() => toggleLevel(lv)} className="hover:text-foreground">
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
                {[...filterClearTypes].map((ct) => (
                  <Badge key={ct} variant="secondary" className="text-label gap-1 h-5">
                    {getClearLabel(clientType ?? null, ct)}
                    <button onClick={() => toggleClearType(ct)} className="hover:text-foreground">
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
                {filterTitle && (
                  <Badge variant="secondary" className="text-label gap-1 h-5">
                    &quot;{filterTitle}&quot;
                    <button onClick={() => updateParams({ [P_Q]: null })} className="hover:text-foreground">
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-5 text-label px-2"
                  onClick={clearFilters}
                >
                  초기화
                </Button>
              </div>
            )}

            {/* Song count */}
            <div className="text-label text-muted-foreground">
              {filteredSongs.length}곡
              {dist.songs.length !== filteredSongs.length && (
                <span> / 전체 {dist.songs.length}곡</span>
              )}
            </div>

            {/* Song table */}
            <SongTable songs={filteredSongs} levelOrder={orderedLevels} />
          </>
        )}
      </div>
    </div>
  );
}
