"use client";

import { useMemo, useRef, memo, useCallback, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  ExternalLink, Music, Package, FileCode, Youtube, FileSpreadsheet,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { compareTitles } from "@/lib/bms-sort";
import { formatBpm, formatNotes, formatLength } from "@/lib/bms-format";
import { CLEAR_ROW_CLASS, parseArrangement, levelSortIndex, ARRANGEMENT_KANJI, exportToExcel } from "@/lib/fumen-table-utils";
import { CLEAR_TYPE_LABELS } from "@/components/charts/ClearDistributionChart";
import type { DifficultyTableDetail, TableFumen, TableFumenScore } from "@/types";
import { clearText } from "@/components/dashboard/RecentActivity";

type SortKey = "level" | "title" | "lamp" | "score" | "rate" | "rank" | "min_bp" | "plays" | "option" | "bpm" | "notes" | "length" | "env";
type SortDir = "asc" | "desc";

interface TableDetailProps {
  tableId: string;
  isLoggedIn: boolean;
  selectedLevel: string | null;
  onLevelChange: (level: string | null) => void;
}

function SourceClientBadge({ score }: { score: TableFumenScore }) {
  const { source_client, source_client_detail } = score;
  if (!source_client) return null;

  const isMix = source_client === "MIX";
  const badge = (
    <span className={`text-label${isMix ? " cursor-help" : ""}`}>
      {source_client}{isMix && <span className="ml-0.5 text-accent/70 leading-none">●</span>}
    </span>
  );

  if (source_client !== "MIX" || !source_client_detail) return badge;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>{badge}</TooltipTrigger>
        <TooltipContent side="left" className="text-label">
          <div className="space-y-0.5">
            {source_client_detail.clear_type && (
              <div>Lamp: {source_client_detail.clear_type}</div>
            )}
            {source_client_detail.exscore && (
              <div>Score: {source_client_detail.exscore}</div>
            )}
            {source_client_detail.min_bp && (
              <div>BP: {source_client_detail.min_bp}</div>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function songHash(song: TableFumen): string {
  return song.sha256 || song.md5 || "";
}

const RANK_ORDER: Record<string, number> = {
  MAX: 9, AAA: 8, AA: 7, A: 6, B: 5, C: 4, D: 3, E: 2, F: 1,
};

export function TableDetail({ tableId, isLoggedIn, selectedLevel, onLevelChange }: TableDetailProps) {
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
          if (cmp === 0) cmp = compareTitles(a.title ?? "", b.title ?? "");
          break;
        }
        case "title":
          cmp = compareTitles(a.title ?? "", b.title ?? "");
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
        불러오는 중...
      </div>
    );
  }

  if (tableError) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-muted-foreground">
        <p>난이도표를 불러오는 데 실패했습니다.</p>
        <p className="text-label">{(tableError as Error).message}</p>
      </div>
    );
  }

  if (!table) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        난이도표를 찾을 수 없습니다.
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
          {table.source_url && (
            <div className="mt-1">
              <a
                href={table.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-label text-muted-foreground hover:text-foreground transition-colors"
              >
                난이도표 링크 <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          )}
        </div>
        <div className="shrink-0 text-right text-label text-muted-foreground space-y-0.5">
          {table.song_count != null && (
            <div>{table.song_count.toLocaleString()} 차분</div>
          )}
          {table.updated_at && (
            <div>최근 동기화: {new Date(table.updated_at).toLocaleDateString("ko-KR")}</div>
          )}
        </div>
      </div>

      {!hasData ? (
        <div className="flex flex-col items-center justify-center flex-1 gap-3 text-muted-foreground">
          <Music className="h-12 w-12 opacity-30" />
          <p className="text-body">난이도표 데이터가 아직 없습니다.</p>
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
              <span>전체</span>
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
                    {table.symbol}{level.replace(table.symbol ?? "", "")}
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
                불러오는 중...
              </div>
            ) : displayedSongs.length === 0 ? (
              <div className="flex items-center justify-center h-full text-muted-foreground text-body">
                차분이 없습니다.
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
  const parentRef = useRef<HTMLDivElement>(null);

  // eslint-disable-next-line react-hooks/incompatible-library
  const rowVirtualizer = useVirtualizer({
    count: songs.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 44,
    overscan: 10,
  });

  const virtualItems = rowVirtualizer.getVirtualItems();
  const paddingTop = virtualItems.length > 0 ? virtualItems[0].start : 0;
  const paddingBottom = virtualItems.length > 0
    ? rowVirtualizer.getTotalSize() - virtualItems[virtualItems.length - 1].end
    : 0;
  const colCount = hasUserScores ? 16 : 8;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Export toolbar — above table */}
      <div className="flex items-center justify-between px-4 py-1 border-b shrink-0">
        <span className="text-label text-muted-foreground">{songs.length}곡</span>
        <button
          className="flex items-center gap-1.5 text-label text-muted-foreground hover:text-foreground transition-colors px-3 py-1 rounded-md border border-border/50 hover:border-border hover:bg-secondary/30"
          title="Export to Excel (.xlsx)"
          disabled={songs.length === 0}
          onClick={() => {
            const columns = [
              { key: "level", header: "Level" },
              { key: "title", header: "Title" },
              { key: "artist", header: "Artist" },
              ...(hasUserScores ? [
                { key: "lamp", header: "Lamp" },
                { key: "bp", header: "BP" },
                { key: "rate", header: "Rate" },
                { key: "rank", header: "Rank" },
                { key: "score", header: "Score" },
                { key: "plays", header: "Plays" },
                { key: "option", header: "Option" },
                { key: "env", header: "Env" },
              ] : []),
              { key: "bpm", header: "BPM" },
              { key: "notes", header: "Notes" },
              { key: "length", header: "Length" },
            ];
            const data = songs.map((song) => {
              const s = song.user_score;
              const arrangement = s ? parseArrangement(s.options, s.client_type) : null;
              return {
                level: `${table.symbol ?? ""}${song.level.replace(table.symbol ?? "", "")}`,
                title: song.title ?? "",
                artist: song.artist ?? "",
                lamp: s ? (CLEAR_TYPE_LABELS[s.best_clear_type ?? 0] ?? "") : "",
                bp: s?.best_min_bp ?? "",
                rate: s?.rate != null ? `${s.rate.toFixed(2)}%` : "",
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
          Export to Excel
        </button>
      </div>

      {/* Scrollable table */}
      <div
        ref={parentRef}
        className="flex-1 overflow-y-auto overflow-x-hidden"
        style={{ overscrollBehavior: "contain" }}
      >
        <table className="w-full border-collapse" style={{ tableLayout: "fixed" }}>
          <colgroup>
            <col style={{ width: 62 }} />
            <col />
            {hasUserScores && (
              <>
                <col style={{ width: 80 }} />
                <col style={{ width: 52 }} />
                <col style={{ width: 68 }} />
                <col style={{ width: 56 }} />
                <col style={{ width: 62 }} />
                <col style={{ width: 60 }} />
                <col style={{ width: 68 }} />
                <col style={{ width: 52 }} />
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
              <Th col="level" label="Level" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
              <Th col="title" label="Title / Artist" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
              {hasUserScores && (
                <>
                  <Th col="lamp" label="Lamp" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <Th col="min_bp" label="BP" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <Th col="rate" label="Rate" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <Th col="rank" label="Rank" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <Th col="score" label="Score" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <Th col="plays" label="Plays" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <Th col="option" label="Option" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <Th col="env" label="Env" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                </>
              )}
              <Th col="bpm" label="BPM" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
              <Th col="notes" label="Notes" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
              <Th col="length" label="Length" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
              <th className="px-2 py-1.5 text-center font-medium whitespace-nowrap">URL1</th>
              <th className="px-2 py-1.5 text-center font-medium whitespace-nowrap">URL2</th>
              <th className="px-2 py-1.5 text-center font-medium whitespace-nowrap">Youtube</th>
            </tr>
          </thead>

          <tbody>
            {paddingTop > 0 && (
              <tr><td colSpan={colCount} style={{ height: paddingTop, padding: 0, border: 0 }} /></tr>
            )}
            {virtualItems.map((virtualRow) => {
              const song = songs[virtualRow.index];
              const levelLabel = `${table.symbol ?? ""}${song.level.replace(table.symbol ?? "", "")}`;
              const s = song.user_score;
              const hash = songHash(song);
              const { total: notesTotal, detail: notesDetail } = formatNotes(
                song.notes_total, song.notes_n, song.notes_ln, song.notes_s, song.notes_ls
              );
              const rowClass = CLEAR_ROW_CLASS[s?.best_clear_type ?? 0] ?? "";
              const arrangement = s ? parseArrangement(s.options, s.client_type) : null;
              const arrangementLabel = arrangement ? (ARRANGEMENT_KANJI[arrangement] ?? arrangement) : null;

              return (
                <tr
                  key={virtualRow.key}
                  style={{ height: virtualRow.size }}
                  className={cn(
                    "border-b border-border/30",
                    rowClass || "hover:bg-secondary/50",
                  )}
                >
                  {/* Level */}
                  <td className="px-2">
                    <span className="text-label">{levelLabel}</span>
                  </td>

                  {/* Title & Artist */}
                  <td className="px-2">
                    <div className="min-w-0 overflow-hidden">
                      {hash ? (
                        <Link
                          href={`/songs/${hash}`}
                          className="text-label truncate hover:text-primary transition-colors block"
                        >
                          {song.title || "(제목 없음)"}
                        </Link>
                      ) : (
                        <p className="text-label truncate">{song.title || "(제목 없음)"}</p>
                      )}
                      <p className="text-caption row-muted truncate">{song.artist}</p>
                      {song.user_tags.length > 0 && (
                        <div className="flex gap-1 flex-wrap">
                          {song.user_tags.map((t) => (
                            <span
                              key={t.id}
                              className="text-caption px-1.5 py-0 rounded-full border border-primary/30 text-primary/80 bg-primary/10"
                            >
                              {t.tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </td>

                  {/* User score columns */}
                  {hasUserScores && (
                    <>
                      <td className="px-2">
                        {s ? clearText(s.best_clear_type, s.source_client ?? "") : (
                          <span className="text-label row-muted">-</span>
                        )}
                      </td>
                      <td className="px-2 text-label">
                        {s?.best_min_bp ?? <span className="row-muted">—</span>}
                      </td>
                      <td className="px-2 text-label">
                        {s?.rate != null ? `${s.rate.toFixed(2)}%` : <span className="row-muted">—</span>}
                      </td>
                      <td className="px-2 text-label">
                        {s?.rank ?? <span className="row-muted">—</span>}
                      </td>
                      <td className="px-2 text-label">
                        {s?.best_exscore ?? <span className="row-muted">—</span>}
                      </td>
                      <td className="px-2 text-label">
                        {s?.play_count ?? <span className="row-muted">—</span>}
                      </td>
                      <td className="px-2 text-label">
                        {arrangementLabel ?? <span className="row-muted">—</span>}
                      </td>
                      <td className="px-2">
                        {s ? <SourceClientBadge score={s} /> : (
                          <span className="text-label row-muted">-</span>
                        )}
                      </td>
                    </>
                  )}

                  {/* BPM */}
                  <td className="px-2 text-label">
                    {formatBpm(song.bpm_main, song.bpm_min, song.bpm_max)}
                  </td>

                  {/* Notes */}
                  <td className="px-2 text-label">
                    {notesTotal === "-" ? "—" : (
                      notesDetail ? (
                        <TooltipProvider>
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
                        </TooltipProvider>
                      ) : notesTotal
                    )}
                  </td>

                  {/* Length */}
                  <td className="px-2 text-label">
                    {formatLength(song.length)}
                  </td>

                  {/* URL1 */}
                  <td className="px-2 text-center">
                    {song.file_url ? (
                      <a
                        href={song.file_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:opacity-70 transition-opacity inline-flex justify-center"
                        title="URL1"
                      >
                        <Package className="h-3.5 w-3.5" />
                      </a>
                    ) : (
                      <span className="text-muted-foreground/30 text-label">–</span>
                    )}
                  </td>

                  {/* URL2 */}
                  <td className="px-2 text-center">
                    {song.file_url_diff ? (
                      <a
                        href={song.file_url_diff}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:opacity-70 transition-opacity inline-flex justify-center"
                        title="URL2"
                      >
                        <FileCode className="h-3.5 w-3.5" />
                      </a>
                    ) : (
                      <span className="text-muted-foreground/30 text-label">–</span>
                    )}
                  </td>

                  {/* Youtube */}
                  <td className="px-2 text-center">
                    {song.youtube_url ? (
                      <a
                        href={song.youtube_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-red-500 hover:text-red-400 transition-colors inline-flex justify-center"
                        title="Youtube"
                      >
                        <Youtube className="h-3.5 w-3.5" />
                      </a>
                    ) : (
                      <span className="text-muted-foreground/30 text-label">–</span>
                    )}
                  </td>
                </tr>
              );
            })}
            {paddingBottom > 0 && (
              <tr><td colSpan={colCount} style={{ height: paddingBottom, padding: 0, border: 0 }} /></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
});
