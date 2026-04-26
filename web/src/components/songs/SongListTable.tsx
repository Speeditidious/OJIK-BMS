"use client";

import { useRef, memo, useEffect } from "react";
import Link from "next/link";
import { useVirtualizer, defaultRangeExtractor } from "@tanstack/react-virtual";
import { Package, FileCode, Youtube } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { SourceClientBadge } from "@/components/common/SourceClientBadge";
import { TableLevelBadges } from "@/components/common/TableLevelBadges";
import { cn } from "@/lib/utils";
import { formatBpm, formatNotes, formatLength } from "@/lib/bms-format";
import { CLEAR_ROW_CLASS, parseArrangement, ARRANGEMENT_KANJI } from "@/lib/fumen-table-utils";
import { formatRatePercent } from "@/lib/rate-format";
import { displayClearType } from "@/lib/clear-type-display";
import { clearText } from "@/components/dashboard/RecentActivity";
import type { FumenListItem, FumenSearchField } from "@/types";

export interface SongListTableProps {
  items: FumenListItem[];
  isLoggedIn: boolean;
  isLoading?: boolean;
  tableSymbolMap: Record<string, string>;
  sortKey?: string;
  sortDir?: "asc" | "desc";
  onSort?: (sortKey: FumenSearchField | "level", sortDir: "asc" | "desc") => void;
}

function songHash(item: FumenListItem): string {
  return item.sha256 || item.md5 || "";
}

function SortIcon({ col, sortKey, sortDir }: { col: string; sortKey?: string; sortDir?: "asc" | "desc" }) {
  if (sortKey !== col) return <span className="ml-0.5 text-muted-foreground/35">⇅</span>;
  return <span className="ml-0.5">{sortDir === "asc" ? "↑" : "↓"}</span>;
}

function Th({
  col, label, sortKey, sortDir, onSort, className,
}: {
  col: string; label: string; sortKey?: string; sortDir?: "asc" | "desc";
  onSort?: (k: FumenSearchField | "level", d: "asc" | "desc") => void; className?: string;
}) {
  function handleClick() {
    if (!onSort) return;
    const nextDir = sortKey === col && sortDir === "asc" ? "desc" : "asc";
    onSort(col as FumenSearchField | "level", nextDir);
  }
  return (
    <th
      className={cn(
        "px-2 py-1.5 text-left font-medium whitespace-nowrap select-none transition-colors",
        onSort ? "cursor-pointer hover:text-foreground" : "",
        className,
      )}
      onClick={handleClick}
    >
      {label}
      {onSort && <SortIcon col={col} sortKey={sortKey} sortDir={sortDir} />}
    </th>
  );
}

interface SongRowProps {
  item: FumenListItem;
  index: number;
  tableSymbolMap: Record<string, string>;
  isLoggedIn: boolean;
}

const SongRow = memo(function SongRow({ item, index, tableSymbolMap, isLoggedIn }: SongRowProps) {
  const s = item.user_score;
  const hash = songHash(item);

  const levels = (item.table_entries ?? []).map((e) => ({
    symbol: tableSymbolMap[e.table_id] ?? "",
    slug: e.table_id,
    level: e.level,
  }));

  const { total: notesTotal, detail: notesDetail } = formatNotes(
    item.notes_total, item.notes_n, item.notes_ln, item.notes_s, item.notes_ls
  );

  const displayType = displayClearType(s?.best_clear_type ?? null, { exscore: s?.best_exscore, rate: s?.rate });
  const rowClass = CLEAR_ROW_CLASS[displayType ?? 0] ?? "";
  const arrangement = s ? parseArrangement(s.options, s.client_type) : null;
  const arrangementLabel = arrangement ? (ARRANGEMENT_KANJI[arrangement] ?? arrangement) : null;

  return (
    <tr
      data-index={index}
      style={{ height: 44 }}
      className={cn("border-b border-border/30", rowClass || "hover:bg-secondary/50")}
    >
      {/* Level */}
      <td className="px-2 align-middle">
        <div className="truncate">
          <TableLevelBadges levels={levels} maxVisible={3} />
        </div>
      </td>

      {/* Title / Artist */}
      <td className="px-2 align-middle" data-title={item.title ?? ""} data-artist={item.artist ?? ""}>
        <div className="min-w-0 overflow-hidden">
          <div className="max-w-full truncate">
            {hash ? (
              <Link href={`/songs/${hash}`} className="text-label hover:text-primary transition-colors">
                {item.title || "(제목 없음)"}
              </Link>
            ) : (
              <span className="text-label">{item.title || "(제목 없음)"}</span>
            )}
          </div>
          {item.artist && <div className="text-caption row-muted max-w-full truncate">{item.artist}</div>}
          {item.user_tags.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              {item.user_tags.map((t) => (
                <span key={t.id} className="text-caption px-1.5 py-0 rounded-full border border-primary/30 text-primary/80 bg-primary/10">
                  {t.tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </td>

      {/* User score columns */}
      {isLoggedIn && (
        <>
          <td className="px-2 align-middle">
            {s ? clearText(s.best_clear_type, s.source_client ?? "", { exscore: s.best_exscore, rate: s.rate }) : <span className="text-label row-muted">-</span>}
          </td>
          <td className="px-2 align-middle text-label">{s?.best_min_bp ?? <span className="row-muted">—</span>}</td>
          <td className="px-2 align-middle text-label">{s?.rate != null ? formatRatePercent(s.rate) : <span className="row-muted">—</span>}</td>
          <td className="px-2 align-middle text-label">{s?.rank ?? <span className="row-muted">—</span>}</td>
          <td className="px-2 align-middle text-label">{s?.best_exscore ?? <span className="row-muted">—</span>}</td>
          <td className="px-2 align-middle text-label">{s?.play_count ?? <span className="row-muted">—</span>}</td>
          <td className="px-2 align-middle text-label">{arrangementLabel ?? <span className="row-muted">—</span>}</td>
          <td className="px-2 align-middle">
            {s ? (
              <SourceClientBadge sourceClient={s.source_client} sourceClientDetail={s.source_client_detail} />
            ) : (
              <span className="text-label row-muted">-</span>
            )}
          </td>
        </>
      )}

      {/* Fumen meta */}
      <td className="px-2 align-middle text-label">{formatBpm(item.bpm_main, item.bpm_min, item.bpm_max)}</td>
      <td className="px-2 align-middle text-label">
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
      <td className="px-2 align-middle text-label">{formatLength(item.length)}</td>
      <td className="px-2 align-middle text-center">
        {item.file_url ? (
          <a href={item.file_url} target="_blank" rel="noopener noreferrer" className="hover:opacity-70 transition-opacity inline-flex justify-center" title="URL1">
            <Package className="h-3.5 w-3.5" />
          </a>
        ) : <span className="text-muted-foreground/30 text-label">–</span>}
      </td>
      <td className="px-2 align-middle text-center">
        {item.file_url_diff ? (
          <a href={item.file_url_diff} target="_blank" rel="noopener noreferrer" className="hover:opacity-70 transition-opacity inline-flex justify-center" title="URL2">
            <FileCode className="h-3.5 w-3.5" />
          </a>
        ) : <span className="text-muted-foreground/30 text-label">–</span>}
      </td>
      <td className="px-2 align-middle text-center">
        {item.youtube_url ? (
          <a href={item.youtube_url} target="_blank" rel="noopener noreferrer" className="text-red-500 hover:text-red-400 transition-colors inline-flex justify-center" title="Youtube">
            <Youtube className="h-3.5 w-3.5" />
          </a>
        ) : <span className="text-muted-foreground/30 text-label">–</span>}
      </td>
    </tr>
  );
});

export function SongListTable({
  items,
  isLoggedIn,
  isLoading,
  tableSymbolMap,
  sortKey,
  sortDir,
  onSort,
}: SongListTableProps) {
  const parentRef = useRef<HTMLDivElement>(null);
  const pinnedRangeRef = useRef<[number, number] | null>(null);

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
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 44,
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
  const colCount = isLoggedIn ? 16 : 8;

  if (isLoading && items.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-muted-foreground text-body">
        불러오는 중...
      </div>
    );
  }

  if (!isLoading && items.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-muted-foreground text-body">
        검색 결과가 없습니다.
      </div>
    );
  }

  return (
    <TooltipProvider>
      <div className="h-full border border-border/40 rounded-lg overflow-hidden">
        <div
          ref={parentRef}
          className="h-full overflow-y-auto overflow-x-auto"
          style={{ overscrollBehavior: "contain" }}
        >
          <table className="w-full border-collapse" style={{ tableLayout: "fixed" }}>
            <colgroup>
              <col style={{ width: 140 }} />
              <col />
              {isLoggedIn && (
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
                <Th col="level" label="레벨" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                <Th col="title" label="제목 / 아티스트" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                {isLoggedIn && (
                  <>
                    <Th col="clear" label="클리어" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                    <Th col="bp" label="BP" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                    <Th col="rate" label="판정" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                    <Th col="rank" label="랭크" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                    <Th col="score" label="점수" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                    <Th col="plays" label="플레이" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                    <Th col="option" label="배치" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                    <Th col="env" label="구동기" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  </>
                )}
                <Th col="bpm" label="BPM" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                <Th col="notes" label="노트 수" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                <Th col="length" label="곡 길이" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                <th className="px-2 py-1.5 text-center font-medium whitespace-nowrap">URL1</th>
                <th className="px-2 py-1.5 text-center font-medium whitespace-nowrap">URL2</th>
                <th className="px-2 py-1.5 text-center font-medium whitespace-nowrap">Youtube</th>
              </tr>
            </thead>

            <tbody>
              {paddingTop > 0 && (
                <tr><td colSpan={colCount} style={{ height: paddingTop, padding: 0, border: 0 }} /></tr>
              )}
              {virtualItems.map((virtualRow) => (
                <SongRow
                  key={virtualRow.key}
                  item={items[virtualRow.index]}
                  index={virtualRow.index}
                  tableSymbolMap={tableSymbolMap}
                  isLoggedIn={isLoggedIn}
                />
              ))}
              {paddingBottom > 0 && (
                <tr><td colSpan={colCount} style={{ height: paddingBottom, padding: 0, border: 0 }} /></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </TooltipProvider>
  );
}
