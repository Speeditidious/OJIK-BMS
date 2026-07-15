"use client";

import { useMemo, useRef, memo, useCallback, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useVirtualizer, defaultRangeExtractor } from "@tanstack/react-virtual";
import {
  ExternalLink, Music, Package, FileCode, Youtube, FileSpreadsheet,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { FumenRowDetail } from "@/components/fumen/FumenRowDetail";
import { UnavailableValue } from "@/components/common/UnavailableValue";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { compareTitles } from "@/lib/bms-sort";
import { formatBpm, formatNotes, formatLength } from "@/lib/bms-format";
import { CLEAR_ROW_CLASS, parseArrangement, levelSortIndex, ARRANGEMENT_KANJI, exportToExcel, makeTableCopyHandler } from "@/lib/fumen-table-utils";
import { fumenArtistText, fumenTitleText } from "@/lib/fumen-display";
import { formatTableLevelWithSymbolForDisplay } from "@/lib/table-level-display";
import { formatRatePercent } from "@/lib/rate-format";
import { displayClearType } from "@/lib/clear-type-display";
import { songHref } from "@/lib/song-href";
import { shouldToggleFumenRow } from "@/lib/fumen-row-toggle-core.mjs";
import { CLEAR_TYPE_LABELS } from "@/components/charts/ClearDistributionChart";
import type { DifficultyTableDetail, TableFumen } from "@/types";
import { clearText } from "@/components/dashboard/RecentActivity";

type SortKey = "level" | "title" | "lamp" | "score" | "rate" | "rank" | "min_bp" | "plays" | "option" | "bpm" | "notes" | "length" | "env";
type SortDir = "asc" | "desc";

interface TableDetailProps {
  tableId: string;
  isLoggedIn: boolean;
  selectedLevel: string | null;
  onLevelChange: (level: string | null) => void;
}

const handleTableCopy = makeTableCopyHandler(1); // col 0=Level, col 1=Title/Artist

const RANK_ORDER: Record<string, number> = {
  MAX: 10, "MAX-": 9, AAA: 8, AA: 7, A: 6, B: 5, C: 4, D: 3, E: 2, F: 1,
};

export function TableDetail({ tableId, isLoggedIn, selectedLevel, onLevelChange }: TableDetailProps) {
  const { t } = useTranslation();
  const [sortKey, setSortKey] = useState<SortKey>("level");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const { data: table, isLoading: tableLoading, error: tableError } = useQuery<DifficultyTableDetail>({
    queryKey: ["table", tableId],
    queryFn: () => api.get(`/tables/${tableId}`),
    staleTime: 5 * 60 * 1000,
  });

  const { data: songs, isLoading: songsLoading } = useQuery<TableFumen[]>({
    queryKey: ["table-songs", tableId],
    queryFn: () => api.get(`/tables/${tableId}/songs`),
    enabled: (table?.level_order.length ?? 0) > 0,
    staleTime: 5 * 60 * 1000,
  });

  const hasData = (table?.level_order.length ?? 0) > 0;

  const songsByLevel = useMemo(
    () =>
      songs?.reduce<Record<string, TableFumen[]>>((acc, song) => {
        if (!acc[song.level]) acc[song.level] = [];
        acc[song.level].push(song);
        return acc;
      }, {}) ?? {},
    [songs]
  );

  const levelOrder = useMemo(() => table?.level_order ?? [], [table?.level_order]);

  const displayedSongs = useMemo(() => {
    const base = selectedLevel
      ? (songsByLevel[selectedLevel] ?? [])
      : songs ?? [];

    return base.slice().sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "level": {
          const ai = levelSortIndex(a.level, levelOrder);
          const bi = levelSortIndex(b.level, levelOrder);
          cmp = ai - bi;
          if (cmp === 0) cmp = compareTitles(fumenTitleText(a.title, ""), fumenTitleText(b.title, ""));
          break;
        }
        case "title":
          cmp = compareTitles(fumenTitleText(a.title, ""), fumenTitleText(b.title, ""));
          break;
        case "lamp":
          cmp = (a.user_score?.best_clear_type ?? -1) - (b.user_score?.best_clear_type ?? -1);
          break;
        case "score":
          cmp = (a.user_score?.best_exscore ?? -1) - (b.user_score?.best_exscore ?? -1);
          break;
        case "rate":
          cmp = (a.user_score?.rate ?? -1) - (b.user_score?.rate ?? -1);
          break;
        case "rank": {
          const ra = RANK_ORDER[a.user_score?.rank ?? ""] ?? 0;
          const rb = RANK_ORDER[b.user_score?.rank ?? ""] ?? 0;
          cmp = ra - rb;
          break;
        }
        case "min_bp":
          cmp = (a.user_score?.best_min_bp ?? Infinity) - (b.user_score?.best_min_bp ?? Infinity);
          break;
        case "plays":
          cmp = (a.user_score?.play_count ?? -1) - (b.user_score?.play_count ?? -1);
          break;
        case "option":
          cmp = (parseArrangement(a.user_score?.options ?? null, a.user_score?.client_type ?? null) ?? "").localeCompare(
            parseArrangement(b.user_score?.options ?? null, b.user_score?.client_type ?? null) ?? ""
          );
          break;
        case "bpm":
          cmp = (a.bpm_main ?? -1) - (b.bpm_main ?? -1);
          break;
        case "notes":
          cmp = (a.notes_total ?? -1) - (b.notes_total ?? -1);
          break;
        case "length":
          cmp = (a.length ?? -1) - (b.length ?? -1);
          break;
        case "env":
          cmp = (a.user_score?.source_client ?? "").localeCompare(b.user_score?.source_client ?? "");
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [selectedLevel, songsByLevel, songs, sortKey, sortDir, levelOrder]);

  const hasUserScores = useMemo(
    () => isLoggedIn && displayedSongs.some((s) => s.user_score !== null),
    [isLoggedIn, displayedSongs]
  );

  const handleSort = useCallback((key: SortKey) => {
    setSortKey((prev) => {
      if (prev === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
        return key;
      }
      setSortDir("asc");
      return key;
    });
  }, []);

  if (tableLoading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        {t("tables.detail.loading")}
      </div>
    );
  }

  if (tableError) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-muted-foreground">
        <p>{t("tables.detail.loadFailed")}</p>
        <p className="text-label">{(tableError as Error).message}</p>
      </div>
    );
  }

  if (!table) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        {t("tables.detail.notFound")}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b flex items-center gap-3 shrink-0">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {table.symbol && (
              <Badge variant="secondary" className="font-mono text-body">
                {table.symbol}
              </Badge>
            )}
            <h2 className="text-xl font-bold truncate">{table.name}</h2>
          </div>
          {(table.source_url || table.representative_site_url) && (
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
              {table.source_url && (
                <a
                  href={table.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex w-fit items-center gap-1 text-label text-muted-foreground hover:text-foreground transition-colors"
                >
                  {t("tables.detail.tableLink")} <ExternalLink className="h-3 w-3" />
                </a>
              )}
              {table.representative_site_url && (
                <a
                  href={table.representative_site_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex w-fit items-center gap-1 text-label text-muted-foreground hover:text-foreground transition-colors"
                >
                  {t("tables.detail.representativeSite")} <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          )}
        </div>
        <div className="shrink-0 text-right text-label text-muted-foreground space-y-0.5">
          {table.song_count != null && (
            <div>{t("tables.detail.songCount", { count: table.song_count })}</div>
          )}
          {table.updated_at && (
            <div>{t("tables.detail.lastSynced", { date: new Date(table.updated_at).toLocaleDateString() })}</div>
          )}
        </div>
      </div>

      {!hasData ? (
        <div className="flex flex-col items-center justify-center flex-1 gap-3 text-muted-foreground">
          <Music className="h-12 w-12 opacity-30" />
          <p className="text-body">{t("tables.detail.empty")}</p>
        </div>
      ) : (
        <div className="flex flex-1 overflow-hidden">
          {/* Level selector */}
          <div className="w-32 shrink-0 border-r overflow-y-auto overscroll-contain [&::-webkit-scrollbar]:hidden">
            <div
              className={cn(
                "px-3 py-2 text-body cursor-pointer transition-colors flex items-center justify-between",
                selectedLevel === null
                  ? "bg-primary/10 text-primary font-medium"
                  : "hover:bg-secondary text-muted-foreground"
              )}
              onClick={() => onLevelChange(null)}
            >
              <span>{t("tables.detail.allLevels")}</span>
              {songs != null && (
                <span className="text-label opacity-60">{songs.length}</span>
              )}
            </div>
            {table.level_order.map((level) => {
              const count = songsByLevel[level]?.length;
              return (
                <div
                  key={level}
                  className={cn(
                    "px-3 py-2 text-body cursor-pointer transition-colors flex items-center justify-between",
                    selectedLevel === level
                      ? "bg-primary/10 text-primary font-medium"
                      : "hover:bg-secondary text-muted-foreground"
                  )}
                  onClick={() => onLevelChange(level)}
                >
                  <span>
                    {formatTableLevelWithSymbolForDisplay({
                      tableSlug: table.slug,
                      tableName: table.name,
                      tableSymbol: table.symbol,
                      level,
                    })}
                  </span>
                  {count != null && (
                    <span className="text-label opacity-60">{count}</span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Song list */}
          <div className="flex-1 overflow-hidden">
            {songsLoading ? (
              <div className="flex items-center justify-center h-full text-muted-foreground text-body">
                {t("tables.detail.loading")}
              </div>
            ) : displayedSongs.length === 0 ? (
              <div className="flex items-center justify-center h-full text-muted-foreground text-body">
                {t("common.states.noData")}
              </div>
            ) : (
              <SongVirtualList
                songs={displayedSongs}
                table={table}
                hasUserScores={hasUserScores}
                sortKey={sortKey}
                sortDir={sortDir}
                onSort={handleSort}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// --- Virtualized song table ---

const DETAIL_HEIGHT_ESTIMATE_TD = 180;

interface SongRowProps {
  song: TableFumen;
  index: number;
  tableSymbol: string | undefined;
  tableSlug: string | null | undefined;
  tableName: string | undefined;
  hasUserScores: boolean;
  isExpanded: boolean;
  onToggle: () => void;
  colCount: number;
}

const SongRow = memo(function SongRow({ song, index, tableSymbol, tableSlug, tableName, hasUserScores, isExpanded, onToggle, colCount }: SongRowProps) {
  const { t } = useTranslation();
  const s = song.user_score;
  const href = songHref(song);
  const levelLabel = formatTableLevelWithSymbolForDisplay({
    tableSlug,
    tableName,
    tableSymbol,
    level: song.level,
  });
  const { total: notesTotal, detail: notesDetail } = formatNotes(
    song.notes_total, song.notes_n, song.notes_ln, song.notes_s, song.notes_ls
  );
  const displayType = displayClearType(s?.best_clear_type ?? null, { exscore: s?.best_exscore, rate: s?.rate });
  const rowClass = CLEAR_ROW_CLASS[displayType ?? 0] ?? "";
  const arrangement = s ? parseArrangement(s.options, s.client_type) : null;
  const arrangementLabel = arrangement ? (ARRANGEMENT_KANJI[arrangement] ?? arrangement) : null;
  const displayTitle = fumenTitleText(song.title, t("fumen.detail.untitled"));
  const displayArtist = fumenArtistText(song.artist);

  function handleRowClick(e: React.MouseEvent<HTMLTableRowElement>) {
    if (!shouldToggleFumenRow(e.target as HTMLElement)) return;
    onToggle();
  }

  return (
    <>
      <tr
        data-index={index}
        style={{ height: 44 }}
        className={cn("border-b border-border/30 cursor-pointer", rowClass || "hover:bg-secondary/50")}
        onClick={handleRowClick}
      >
        <td className="px-2">
          <span className="text-label">{levelLabel}</span>
        </td>
        <td className="px-2" data-title={displayTitle} data-artist={displayArtist}>
          <div className="min-w-0 overflow-hidden">
            <div className="max-w-full truncate">
              <a href={href} className="text-label hover:text-primary transition-colors">
                {displayTitle}
              </a>
            </div>
            {displayArtist && <div className="text-caption row-muted max-w-full truncate">{displayArtist}</div>}
            {song.user_tags.length > 0 && (
              <div className="flex gap-1 flex-wrap">
                {song.user_tags.map((t) => (
                  <span key={t.id} className="text-caption px-1.5 py-0 rounded-full border border-primary/30 text-primary/80 bg-primary/10">
                    {t.tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        </td>
        {hasUserScores && (
          <>
            <td className="px-2">
              {s ? clearText(s.best_clear_type, s.source_client ?? "", { exscore: s.best_exscore, rate: s.rate }) : <span className="text-label row-muted">-</span>}
            </td>
            <td className="px-2 text-label">{s?.best_min_bp ?? <span className="row-muted">—</span>}</td>
            <td className="px-2 text-label">{s?.rate != null ? formatRatePercent(s.rate) : <span className="row-muted">—</span>}</td>
            <td className="px-2 text-label">{s?.rank ?? <span className="row-muted">—</span>}</td>
            <td className="px-2 text-label">{s?.best_exscore ?? <span className="row-muted">—</span>}</td>
            <td className="px-2 text-label">{s?.play_count ?? <span className="row-muted">—</span>}</td>
            <td className="px-2 text-label">
              {arrangementLabel ? (
                <span>{arrangementLabel}</span>
              ) : !s?.options && s?.client_type === "beatoraja" ? (
                <UnavailableValue reason="score_metadata_missing" />
              ) : (
                <span className="row-muted">—</span>
              )}
            </td>
          </>
        )}
        <td className="px-2 text-label">{formatBpm(song.bpm_main, song.bpm_min, song.bpm_max)}</td>
        <td className="px-2 text-label">
          {notesTotal === "-" ? "—" : notesDetail ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="cursor-help inline-flex items-center gap-0.5">
                  {notesTotal}
                  <span className="text-caption text-accent/70 leading-none">●</span>
                </span>
              </TooltipTrigger>
              <TooltipContent side="left" className="text-label">
                <div className="space-y-0.5">
                  {notesDetail.split(" ").map((part) => {
                    const [label, val] = part.split(":");
                    return (
                      <div key={label} className="flex gap-2 justify-between">
                        <span className="text-muted-foreground">{label}</span>
                        <span>{val}</span>
                      </div>
                    );
                  })}
                </div>
              </TooltipContent>
            </Tooltip>
          ) : notesTotal}
        </td>
        <td className="px-2 text-label">{formatLength(song.length)}</td>
        <td className="px-2 text-center">
          {song.file_url ? (
            <a href={song.file_url} target="_blank" rel="noopener noreferrer" className="hover:opacity-70 transition-opacity inline-flex justify-center" title="URL1">
              <Package className="h-3.5 w-3.5" />
            </a>
          ) : <span className="text-muted-foreground/30 text-label">–</span>}
        </td>
        <td className="px-2 text-center">
          {song.file_url_diff ? (
            <a href={song.file_url_diff} target="_blank" rel="noopener noreferrer" className="hover:opacity-70 transition-opacity inline-flex justify-center" title="URL2">
              <FileCode className="h-3.5 w-3.5" />
            </a>
          ) : <span className="text-muted-foreground/30 text-label">–</span>}
        </td>
        <td className="px-2 text-center">
          {song.youtube_url ? (
            <a href={song.youtube_url} target="_blank" rel="noopener noreferrer" className="text-red-500 hover:text-red-400 transition-colors inline-flex justify-center" title="Youtube">
              <Youtube className="h-3.5 w-3.5" />
            </a>
          ) : <span className="text-muted-foreground/30 text-label">–</span>}
        </td>
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={colCount} className="p-0 border-b border-border/20">
            <div className="border-t border-primary/20 bg-primary/5">
              <FumenRowDetail fumenId={song.fumen_id} />
            </div>
          </td>
        </tr>
      )}
    </>
  );
});

interface SongVirtualListProps {
  songs: TableFumen[];
  table: DifficultyTableDetail;
  hasUserScores: boolean;
  sortKey: SortKey;
  sortDir: SortDir;
  onSort: (key: SortKey) => void;
}

function SortIcon({ col, sortKey, sortDir }: { col: SortKey; sortKey: SortKey; sortDir: SortDir }) {
  if (sortKey !== col) return <span className="ml-0.5 text-muted-foreground/35">⇅</span>;
  return <span className="ml-0.5">{sortDir === "asc" ? "↑" : "↓"}</span>;
}

function Th({ col, label, sortKey, sortDir, onSort, className }: {
  col: SortKey; label: string; sortKey: SortKey; sortDir: SortDir;
  onSort: (key: SortKey) => void; className?: string;
}) {
  return (
    <th
      className={cn(
        "px-2 py-1.5 text-left font-medium whitespace-nowrap cursor-pointer select-none hover:text-foreground transition-colors",
        className,
      )}
      onClick={() => onSort(col)}
    >
      {label}<SortIcon col={col} sortKey={sortKey} sortDir={sortDir} />
    </th>
  );
}

const SongVirtualList = memo(function SongVirtualList({
  songs, table, hasUserScores, sortKey, sortDir, onSort,
}: SongVirtualListProps) {
  const { t } = useTranslation();
  const parentRef = useRef<HTMLDivElement>(null);
  const pinnedRangeRef = useRef<[number, number] | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const toggleRow = useCallback((fumenId: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(fumenId)) next.delete(fumenId); else next.add(fumenId);
      return next;
    });
  }, []);

  useEffect(() => {
    const toRowIndex = (node: Node | null): number | null => {
      let el = node as HTMLElement | null;
      while (el && el.tagName !== "TR") el = el.parentElement;
      const idx = el?.dataset?.index;
      return idx !== undefined ? Number(idx) : null;
    };
    const handleSelectionChange = () => {
      const sel = document.getSelection();
      if (!sel || sel.isCollapsed || sel.rangeCount === 0) { pinnedRangeRef.current = null; return; }
      if (!parentRef.current?.contains(sel.anchorNode as Node)) { pinnedRangeRef.current = null; return; }
      const anchorIdx = toRowIndex(sel.anchorNode);
      const focusIdx = toRowIndex(sel.focusNode);
      if (anchorIdx !== null && focusIdx !== null) {
        pinnedRangeRef.current = [Math.min(anchorIdx, focusIdx), Math.max(anchorIdx, focusIdx)];
      } else if (anchorIdx !== null) {
        const prev = pinnedRangeRef.current;
        const prevEnd = prev ? Math.max(prev[0], prev[1]) : anchorIdx;
        pinnedRangeRef.current = [Math.min(anchorIdx, prevEnd), Math.max(anchorIdx, prevEnd)];
      }
    };
    const handleMouseUp = () => { pinnedRangeRef.current = null; };
    document.addEventListener("selectionchange", handleSelectionChange);
    document.addEventListener("mouseup", handleMouseUp);
    return () => {
      document.removeEventListener("selectionchange", handleSelectionChange);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  // eslint-disable-next-line react-hooks/incompatible-library
  const rowVirtualizer = useVirtualizer({
    count: songs.length,
    getScrollElement: () => parentRef.current,
    estimateSize: useCallback(
      (i: number) => expandedRows.has(songs[i].fumen_id) ? 44 + DETAIL_HEIGHT_ESTIMATE_TD : 44,
      [expandedRows, songs]
    ),
    overscan: 10,
    rangeExtractor: (range) => {
      const normal = defaultRangeExtractor(range);
      const pinned = pinnedRangeRef.current;
      if (!pinned) return normal;
      const [pinStart, pinEnd] = pinned;
      if (normal.length === 0) return Array.from({ length: pinEnd - pinStart + 1 }, (_, i) => pinStart + i);
      const mergedStart = Math.min(normal[0], pinStart);
      const mergedEnd = Math.max(normal[normal.length - 1], pinEnd);
      return Array.from({ length: mergedEnd - mergedStart + 1 }, (_, i) => mergedStart + i);
    },
  });

  const virtualItems = rowVirtualizer.getVirtualItems();
  const paddingTop = virtualItems.length > 0 ? virtualItems[0].start : 0;
  const paddingBottom = virtualItems.length > 0
    ? rowVirtualizer.getTotalSize() - virtualItems[virtualItems.length - 1].end
    : 0;
  const colCount = hasUserScores ? 15 : 8;

  return (
    <TooltipProvider>
    <div className="flex flex-col h-full overflow-hidden">
      {/* Export toolbar — above table */}
      <div className="flex items-center justify-between px-4 py-1 border-b shrink-0">
        <span className="text-label text-muted-foreground">{t("tables.detail.songCount", { count: songs.length })}</span>
        <button
          className="flex items-center gap-1.5 text-label text-muted-foreground hover:text-foreground transition-colors px-3 py-1 rounded-md border border-border/50 hover:border-border hover:bg-secondary/30"
          title={t("tables.detail.excelExportTitle")}
          disabled={songs.length === 0}
          onClick={() => {
            const columns = [
              { key: "level", header: t("common.fields.level") },
              { key: "title", header: t("common.fields.title") },
              { key: "artist", header: t("common.fields.artist") },
              ...(hasUserScores ? [
                { key: "lamp", header: t("common.fields.clear") },
                { key: "bp", header: t("common.fields.bp") },
                { key: "rate", header: t("common.fields.rate") },
                { key: "rank", header: t("common.fields.rank") },
                { key: "score", header: t("common.fields.score") },
                { key: "plays", header: t("common.fields.plays") },
                { key: "option", header: t("common.fields.option") },
                { key: "env", header: t("common.fields.env") },
              ] : []),
              { key: "bpm", header: "BPM" },
              { key: "notes", header: t("common.fields.notes") },
              { key: "length", header: t("common.fields.length") },
            ];
            const data = songs.map((song) => {
              const s = song.user_score;
              const arrangement = s ? parseArrangement(s.options, s.client_type) : null;
              return {
                level: formatTableLevelWithSymbolForDisplay({
                  tableSlug: table.slug,
                  tableName: table.name,
                  tableSymbol: table.symbol,
                  level: song.level,
                }),
                title: fumenTitleText(song.title, ""),
                artist: fumenArtistText(song.artist),
                lamp: s ? (CLEAR_TYPE_LABELS[s.best_clear_type ?? 0] ?? "") : "",
                bp: s?.best_min_bp ?? "",
                rate: s?.rate != null ? formatRatePercent(s.rate) : "",
                rank: s?.rank ?? "",
                score: s?.best_exscore ?? "",
                plays: s?.play_count ?? "",
                option: arrangement ? (ARRANGEMENT_KANJI[arrangement] ?? arrangement) : "",
                env: s?.source_client ?? "",
                bpm: formatBpm(song.bpm_main, song.bpm_min, song.bpm_max),
                notes: formatNotes(song.notes_total, song.notes_n, song.notes_ln, song.notes_s, song.notes_ls).total,
                length: String(song.length ?? ""),
              };
            });
            exportToExcel(data, columns, `${table.name}_${new Date().toISOString().slice(0, 10)}`);
          }}
        >
          <FileSpreadsheet className="h-3.5 w-3.5" />
          {t("tables.detail.excelExportButton")}
        </button>
      </div>

      {/* Scrollable table */}
      <div
        ref={parentRef}
        className="flex-1 overflow-y-auto overflow-x-auto"
        style={{ overscrollBehavior: "contain" }}
      >
        <table className="w-full border-collapse" style={{ tableLayout: "fixed" }} onCopy={handleTableCopy}>
          <colgroup>
            <col style={{ width: 62 }} />
            <col style={{ minWidth: 190 }} />
            {hasUserScores && (
              <>
                <col style={{ width: 80 }} />
                <col style={{ width: 52 }} />
                <col style={{ width: 68 }} />
                <col style={{ width: 56 }} />
                <col style={{ width: 62 }} />
                <col style={{ width: 60 }} />
                <col style={{ width: 68 }} />
              </>
            )}
            <col style={{ width: 68 }} />
            <col style={{ width: 64 }} />
            <col style={{ width: 70 }} />
            <col style={{ width: 48 }} />
            <col style={{ width: 48 }} />
            <col style={{ width: 72 }} />
          </colgroup>

          <thead className="sticky top-0 z-10 bg-background text-label text-foreground font-medium">
            <tr className="border-b">
              <Th col="level" label={t("common.fields.level")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
              <Th col="title" label={t("common.fields.titleArtist")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
              {hasUserScores && (
                <>
                  <Th col="lamp" label={t("common.fields.clear")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <Th col="min_bp" label={t("common.fields.bp")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <Th col="rate" label={t("common.fields.rate")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <Th col="rank" label={t("common.fields.rank")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <Th col="score" label={t("common.fields.score")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <Th col="plays" label={t("common.fields.plays")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <Th col="option" label={t("common.fields.option")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                </>
              )}
              <Th col="bpm" label="BPM" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
              <Th col="notes" label={t("common.fields.notes")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
              <Th col="length" label={t("common.fields.length")} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
              <th className="px-2 py-1.5 text-center font-medium whitespace-nowrap">URL1</th>
              <th className="px-2 py-1.5 text-center font-medium whitespace-nowrap">URL2</th>
              <th className="px-2 py-1.5 text-center font-medium whitespace-nowrap">Youtube</th>
            </tr>
          </thead>

          {paddingTop > 0 && (
            <tbody>
              <tr><td colSpan={colCount} style={{ height: paddingTop, padding: 0, border: 0 }} /></tr>
            </tbody>
          )}
            {virtualItems.map((virtualRow) => (
              <tbody key={virtualRow.key} data-index={virtualRow.index} ref={rowVirtualizer.measureElement}>
                <SongRow
                  song={songs[virtualRow.index]}
                  index={virtualRow.index}
                  tableSymbol={table.symbol ?? undefined}
                  tableSlug={table.slug}
                  tableName={table.name}
                  hasUserScores={hasUserScores}
                  isExpanded={expandedRows.has(songs[virtualRow.index].fumen_id)}
                  onToggle={() => toggleRow(songs[virtualRow.index].fumen_id)}
                  colCount={colCount}
                />
              </tbody>
            ))}
          {paddingBottom > 0 && (
            <tbody>
              <tr><td colSpan={colCount} style={{ height: paddingBottom, padding: 0, border: 0 }} /></tr>
            </tbody>
          )}
        </table>
      </div>
    </div>
    </TooltipProvider>
  );
});
