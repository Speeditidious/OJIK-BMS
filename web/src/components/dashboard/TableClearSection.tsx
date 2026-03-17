"use client";

import React, { useState, useMemo, useCallback, useDeferredValue } from "react";
import { X, ChevronUp, ChevronDown, ChevronsUpDown, Search } from "lucide-react";
import { useFavoriteTables } from "@/hooks/use-tables";
import { useTableClearDistribution, TableClearSong } from "@/hooks/use-analysis";
import {
  TableClearHistogram,
  ClearTypeLegend,
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

const ARRANGEMENT_KANJI: Record<string, string> = {
  NORMAL:        "正",
  MIRROR:        "鏡",
  RANDOM:        "乱",
  "R-RANDOM":    "R乱",
  "S-RANDOM":    "S乱",
  SPIRAL:        "螺",
  "H-RANDOM":    "H乱",
  "ALL-SCRATCH": "全皿",
  "EX-RAN":      "EX乱",
  "EX-S-RAN":    "EXS乱",
};

// Row background tint by internal clear type (very subtle)
const CLEAR_ROW_BG: Record<number, string> = {
  0: "",
  1: "bg-[hsl(var(--clear-failed)/0.07)]",
  2: "bg-[hsl(var(--clear-assist)/0.10)]",
  3: "bg-[hsl(var(--clear-easy)/0.10)]",
  4: "bg-[hsl(var(--clear-normal)/0.10)]",
  5: "bg-[hsl(var(--clear-hard)/0.10)]",
  6: "bg-[hsl(var(--clear-exhard)/0.10)]",
  7: "bg-[hsl(var(--clear-fc)/0.13)]",
  8: "bg-[hsl(var(--clear-perfect)/0.13)]",
  9: "bg-[hsl(var(--clear-max)/0.13)]",
};

function getRank(scoreRate: number | null): string {
  if (scoreRate === null) return "–";
  if (scoreRate >= 1.0) return "MAX";
  if (scoreRate >= 8 / 9) return "AAA";
  if (scoreRate >= 7 / 9) return "AA";
  if (scoreRate >= 6 / 9) return "A";
  if (scoreRate >= 5 / 9) return "B";
  if (scoreRate >= 4 / 9) return "C";
  if (scoreRate >= 3 / 9) return "D";
  if (scoreRate >= 2 / 9) return "E";
  return "F";
}

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

type SortKey = "level" | "title" | "ex_score" | "score_rate" | "min_bp" | "clear_type";
type SortDir = "asc" | "desc";

function parseLevel(level: string): number {
  const n = parseFloat(level);
  return isNaN(n) ? Infinity : n;
}

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
    // ASCII letters → group 1
    if ((code >= 0x41 && code <= 0x5A) || (code >= 0x61 && code <= 0x7A)) return 1;
    // ASCII punctuation / digits → group 0
    return 0;
  }
  if (code >= 0x3040 && code <= 0x309F) return 3; // Hiragana
  if (code >= 0x30A0 && code <= 0x30FF) return 4; // Katakana
  if ((code >= 0x4E00 && code <= 0x9FFF) || (code >= 0x3400 && code <= 0x4DBF)) return 5; // CJK
  return 2; // other non-ASCII symbols (★ ☆ …)
}

function compareTitles(a: string, b: string): number {
  const aFirst = [...a][0] ?? "";
  const bFirst = [...b][0] ?? "";
  const ga = charSortGroup(aFirst);
  const gb = charSortGroup(bFirst);
  if (ga !== gb) return ga - gb;
  return a.localeCompare(b);
}

function compareSongs(a: TableClearSong, b: TableClearSong, key: SortKey, dir: SortDir): number {
  let result = 0;
  switch (key) {
    case "level": {
      const diff = parseLevel(a.level) - parseLevel(b.level);
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
    case "score_rate":
      result = (a.score_rate ?? -1) - (b.score_rate ?? -1);
      break;
    case "min_bp":
      // nulls last; lower BP is better so ascending = best BP first when reversed
      if (a.min_bp === null && b.min_bp === null) result = 0;
      else if (a.min_bp === null) result = 1;
      else if (b.min_bp === null) result = -1;
      else result = a.min_bp - b.min_bp;
      break;
    case "clear_type":
      result = a.clear_type - b.clear_type;
      break;
  }
  return dir === "asc" ? result : -result;
}

function SortIcon({ colKey, sortKey, sortDir }: { colKey: SortKey; sortKey: SortKey; sortDir: SortDir }) {
  if (colKey !== sortKey) return <ChevronsUpDown className="inline h-3 w-3 ml-0.5 opacity-30" />;
  return sortDir === "asc"
    ? <ChevronUp className="inline h-3 w-3 ml-0.5 text-primary" />
    : <ChevronDown className="inline h-3 w-3 ml-0.5 text-primary" />;
}

const SongTable = React.memo(function SongTable({ songs }: { songs: TableClearSong[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("level");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const sorted = useMemo(
    () => [...songs].sort((a, b) => compareSongs(a, b, sortKey, sortDir)),
    [songs, sortKey, sortDir]
  );

  if (songs.length === 0) {
    return (
      <div className="flex items-center justify-center h-24 text-muted-foreground text-sm">
        해당 조건의 곡이 없습니다
      </div>
    );
  }

  const th = (label: string, key: SortKey, align: "left" | "right" | "center" = "left", width?: string) => (
    <th
      className={cn(
        "px-3 py-2 font-medium text-xs text-muted-foreground select-none cursor-pointer hover:text-foreground transition-colors whitespace-nowrap",
        align === "left" ? "text-left" : align === "right" ? "text-right" : "text-center",
        width
      )}
      onClick={() => handleSort(key)}
    >
      {label}
      <SortIcon colKey={key} sortKey={sortKey} sortDir={sortDir} />
    </th>
  );

  return (
    <div className="overflow-auto max-h-[420px] rounded-md border border-border">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-card border-b border-border z-10">
          <tr>
            {th("레벨", "level", "left", "w-14")}
            {th("곡명", "title", "left")}
            {th("EX Score", "ex_score", "center", "w-20")}
            {th("Rate", "score_rate", "center", "w-20")}
            {th("Rank", "score_rate", "center", "w-14")}
            {th("BP", "min_bp", "center", "w-14")}
            <th className="text-center px-3 py-2 font-medium text-xs text-muted-foreground w-12">배치</th>
            <th className="text-center px-3 py-2 font-medium text-xs text-muted-foreground w-16">구동기</th>
            {th("클리어", "clear_type", "center", "w-24")}
          </tr>
        </thead>
        <tbody>
          {sorted.map((song, idx) => {
            const arrangement = song.options
              ? ARRANGEMENT_KANJI[(song.options.arrangement as string) ?? ""] ?? null
              : null;
            return (
              <tr
                key={song.sha256 || idx}
                className={cn(
                  "border-b border-border/30 last:border-0",
                  CLEAR_ROW_BG[song.clear_type] ?? ""
                )}
              >
                <td className="px-3 py-2 text-xs text-muted-foreground">{song.level}</td>
                <td className="px-3 py-2">
                  <div className="font-medium text-xs leading-tight truncate max-w-[220px]">
                    {song.title || "(제목 없음)"}
                  </div>
                  {song.artist && (
                    <div className="text-[10px] text-muted-foreground truncate max-w-[220px]">
                      {song.artist}
                    </div>
                  )}
                </td>
                <td className="px-3 py-2 text-center text-xs font-mono">
                  {song.ex_score !== null ? (
                    song.ex_score
                  ) : (
                    <span className="text-muted-foreground">--</span>
                  )}
                </td>
                <td className="px-3 py-2 text-center text-xs font-mono">
                  {song.score_rate !== null ? (
                    `${(song.score_rate * 100).toFixed(2)}%`
                  ) : (
                    <span className="text-muted-foreground">--</span>
                  )}
                </td>
                <td className="px-3 py-2 text-center text-xs font-mono">
                  {song.score_rate !== null ? getRank(song.score_rate) : (
                    <span className="text-muted-foreground">--</span>
                  )}
                </td>
                <td className="px-3 py-2 text-center text-xs font-mono">
                  {song.min_bp !== null ? (
                    song.min_bp
                  ) : (
                    <span className="text-muted-foreground">--</span>
                  )}
                </td>
                <td className="px-3 py-2 text-center text-xs">
                  {arrangement ? (
                    <span className="text-muted-foreground">{arrangement}</span>
                  ) : (
                    <span className="text-muted-foreground/40">–</span>
                  )}
                </td>
                <td className="px-3 py-2 text-center">
                  {song.client_type ? (
                    <span className="inline-flex items-center rounded px-1.5 py-0 text-[10px] font-medium border border-border/50 text-muted-foreground">
                      {song.client_type === "beatoraja" ? "BR" : song.client_type.toUpperCase()}
                    </span>
                  ) : (
                    <span className="text-muted-foreground/40">–</span>
                  )}
                </td>
                <td className="px-3 py-2 text-center">
                  {song.clear_type > 0 ? (
                    <span
                      className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium"
                      style={{
                        background: `${CLEAR_TYPE_COLORS[song.clear_type]}30`,
                        color: CLEAR_TYPE_COLORS[song.clear_type],
                        border: `1px solid ${CLEAR_TYPE_COLORS[song.clear_type]}60`,
                      }}
                    >
                      {getClearLabel(song.client_type, song.clear_type)}
                    </span>
                  ) : (
                    <span className="text-[10px] text-muted-foreground">NO PLAY</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
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

function FilterPanel({
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
  const clearTypes = (ALL_CLEAR_TYPES as readonly number[]).filter((ct) => {
    if (clientType === "lr2" && (ct === 2 || ct === 6)) return false;
    return true;
  });

  return (
    <div className="rounded-lg border border-border/50 bg-card/50 p-3 space-y-3">
      {/* Clear type toggles */}
      <div className="flex gap-2 items-start">
        <span className="text-[11px] text-muted-foreground pt-[3px] w-14 shrink-0">클리어</span>
        <div className="flex flex-wrap gap-1">
          {clearTypes.map((ct) => {
            const active = filterClearTypes.has(ct);
            const color = CLEAR_TYPE_COLORS[ct];
            const label = getClearLabel(clientType ?? null, ct);
            return (
              <button
                key={ct}
                onClick={() => onToggleClearType(ct)}
                className={cn(
                  "inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium transition-all border",
                  active
                    ? "opacity-100"
                    : "opacity-50 hover:opacity-75 border-border/40"
                )}
                style={
                  active
                    ? {
                        background: `${color}25`,
                        color,
                        borderColor: `${color}80`,
                      }
                    : { color }
                }
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
        <span className="text-[11px] text-muted-foreground pt-[3px] w-14 shrink-0">레벨</span>
        <div className="flex flex-wrap gap-1 max-h-[72px] overflow-y-auto pr-1">
          {levels.map((lv) => {
            const active = filterLevels.has(lv);
            return (
              <button
                key={lv}
                onClick={() => onToggleLevel(lv)}
                className={cn(
                  "inline-flex items-center rounded px-2 py-0.5 text-[11px] font-mono font-medium transition-all border",
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
        <span className="text-[11px] text-muted-foreground w-14 shrink-0">검색</span>
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground pointer-events-none" />
          <Input
            value={filterTitle}
            onChange={(e) => onTitleChange(e.target.value)}
            placeholder="곡명 / 아티스트"
            className="h-7 pl-6 pr-6 text-xs"
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
}

// ---------------------------------------------------------------------------
// TableClearSection
// ---------------------------------------------------------------------------

interface TableClearSectionProps {
  clientType?: string;
}

export function TableClearSection({ clientType }: TableClearSectionProps) {
  const { data: favTables, isLoading: tablesLoading } = useFavoriteTables();
  const [selectedTableId, setSelectedTableId] = useState<number | null>(null);

  // Multi-select filter state
  const [filterLevels, setFilterLevels] = useState<Set<string>>(new Set());
  const [filterClearTypes, setFilterClearTypes] = useState<Set<number>>(new Set());
  const [filterTitle, setFilterTitle] = useState("");
  const deferredTitle = useDeferredValue(filterTitle);

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

  // Histogram click: exclusive toggle (same bar twice → clear; different bar → exclusive set)
  const handleHistogramSelect = useCallback((level: string, clearType: number) => {
    const isExclusive =
      filterLevels.size === 1 &&
      filterLevels.has(level) &&
      filterClearTypes.size === 1 &&
      filterClearTypes.has(clearType);

    if (isExclusive) {
      setFilterLevels(new Set());
      setFilterClearTypes(new Set());
    } else {
      setFilterLevels(new Set([level]));
      setFilterClearTypes(new Set([clearType]));
    }
  }, [filterLevels, filterClearTypes]);

  const toggleLevel = useCallback((lv: string) => {
    setFilterLevels((prev) => {
      const next = new Set(prev);
      if (next.has(lv)) next.delete(lv); else next.add(lv);
      return next;
    });
  }, []);

  const toggleClearType = useCallback((ct: number) => {
    setFilterClearTypes((prev) => {
      const next = new Set(prev);
      if (next.has(ct)) next.delete(ct); else next.add(ct);
      return next;
    });
  }, []);

  const clearFilters = useCallback(() => {
    setFilterLevels(new Set());
    setFilterClearTypes(new Set());
    setFilterTitle("");
  }, []);

  const handleTableSelect = useCallback((id: number) => {
    setSelectedTableId(id);
    setFilterLevels(new Set());
    setFilterClearTypes(new Set());
    setFilterTitle("");
  }, []);

  if (tablesLoading) {
    return <div className="h-48 bg-muted rounded animate-pulse" />;
  }

  if (!favTables || favTables.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
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
            <span className="text-sm font-bold leading-tight">
              {t.symbol ?? t.name.slice(0, 2)}
            </span>
            <span className="text-xs leading-tight">
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
          <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
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
            />

            {/* Color legend */}
            <ClearTypeLegend clientType={clientType} />

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
              onTitleChange={setFilterTitle}
            />

            {/* Active filters display */}
            {isFiltered && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-muted-foreground">필터:</span>
                {[...filterLevels].map((lv) => (
                  <Badge key={lv} variant="secondary" className="text-xs gap-1 h-5">
                    {formatLevel(lv, tableSymbol)}
                    <button onClick={() => toggleLevel(lv)} className="hover:text-foreground">
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
                {[...filterClearTypes].map((ct) => (
                  <Badge key={ct} variant="secondary" className="text-xs gap-1 h-5">
                    {getClearLabel(clientType ?? null, ct)}
                    <button onClick={() => toggleClearType(ct)} className="hover:text-foreground">
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
                {filterTitle && (
                  <Badge variant="secondary" className="text-xs gap-1 h-5">
                    "{filterTitle}"
                    <button onClick={() => setFilterTitle("")} className="hover:text-foreground">
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-5 text-xs px-2"
                  onClick={clearFilters}
                >
                  초기화
                </Button>
              </div>
            )}

            {/* Song count */}
            <div className="text-xs text-muted-foreground">
              {filteredSongs.length}곡
              {dist.songs.length !== filteredSongs.length && (
                <span> / 전체 {dist.songs.length}곡</span>
              )}
            </div>

            {/* Song table */}
            <SongTable songs={filteredSongs} />
          </>
        )}
      </div>
    </div>
  );
}
