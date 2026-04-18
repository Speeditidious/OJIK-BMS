"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SourceClientBadge } from "@/components/common/SourceClientBadge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import type {
  ScoreUpdatesResponse,
  ScoreUpdateBase,
  ClearTypeUpdateItem,
  ExscoreUpdateItem,
  MaxComboUpdateItem,
  MinBPUpdateItem,
  TableLevelRef,
} from "@/types";
import { clearText } from "@/components/dashboard/RecentActivity";
import type { ClientTypeFilter } from "@/hooks/use-analysis";
import { useScoreUpdates } from "@/hooks/use-analysis";
import { CLEAR_ROW_CLASS, ARRANGEMENT_KANJI, parseArrangement, makeTableCopyHandler } from "@/lib/fumen-table-utils";
import { compareTitles } from "@/lib/bms-sort";
import { useScoreUpdatesPrefs, useUpdateScoreUpdatesPrefs } from "@/hooks/use-preferences";

// ── Helpers ───────────────────────────────────────────────────────────────────

const CLEAR_TYPE_LABELS_SIMPLE: Record<number, string> = {
  0: "NO PLAY", 1: "FAILED", 2: "ASSIST", 3: "EASY", 4: "NORMAL",
  5: "HARD", 6: "EX HARD", 7: "FULL COMBO", 8: "PERFECT", 9: "MAX",
};

/** 개별 <td>에 클리어 타입 CSS 클래스 반환 (globals.css clear-cell-* 참조) */
export function clearTdClass(clearType: number | null | undefined, dim = false): string {
  const ct = clearType ?? 0;
  // NO PLAY(0)은 이미 dim한 색 — dim 변형 불필요
  return (dim && ct !== 0) ? `clear-cell-${ct}-dim` : `clear-cell-${ct}`;
}

/** 개별 <td>에 랭크 기반 CSS 클래스 반환 (globals.css rank-cell-* 참조) */
export function rankTdClass(rank: string | null | undefined, dim = false): string {
  const r = rank ?? "F";
  // F는 이미 dim한 색 — dim 변형 불필요
  return (dim && r !== "F") ? `rank-cell-${r}-dim` : `rank-cell-${r}`;
}



const RANK_SORT_ORDER: Record<string, number> = {
  MAX: -1, AAA: 0, AA: 1, A: 2, B: 3, C: 4, D: 5, E: 6, F: 7,
};

/** table_levels 배열을 기준으로 비교. 즐겨찾기 순서(index 기준) 내에서 높은 레벨이 위. */
function compareByTableLevels(a: TableLevelRef[], b: TableLevelRef[]): number {
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i++) {
    if (i >= a.length) return 1;
    if (i >= b.length) return -1;
    const aLv = parseFloat(a[i].level) || 0;
    const bLv = parseFloat(b[i].level) || 0;
    if (aLv !== bLv) return bLv - aLv;
  }
  return 0;
}


function TableLevelBadges({ levels }: { levels: TableLevelRef[] }) {
  if (levels.length === 0) return <span className="text-label row-muted">-</span>;
  const visible = levels.slice(0, 3);
  const rest = levels.length - visible.length;
  const text = visible.map(({ symbol, level }) => `${symbol}${level}`).join(", ");
  return (
    <span className="text-label">
      {text}
      {rest > 0 && <span className="text-caption row-muted"> +{rest}</span>}
    </span>
  );
}

function formatDate(ts: string | null): string {
  if (!ts) return "";
  const d = new Date(ts);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

// ── Merged course update (clear + score in one row) ────────────────────────────

interface MergedCourseUpdate {
  course_name: string | null;
  dan_title: string | null;
  client_type: string;
  recorded_at: string | null;
  currentClearType?: number | null;
  currentState?: {
    clear_type: number | null;
    exscore: number | null;
    rate: number | null;
    rank: string | null;
    min_bp: number | null;
    max_combo: number | null;
  } | null;
  options?: Record<string, unknown> | null;
  clear?: { prev: number | null; new: number | null };
  score?: { prev: number | null; new: number | null; prev_rank: string | null; new_rank: string | null };
  rate?: { prev: number | null; new: number | null };
  playCount?: { prev: number | null; new: number | null };
}

function isFirstClear(prevClear: number | null | undefined, newClear: number | null | undefined): boolean {
  // ASSIST EASY(2)는 클리어 아님. EASY CLEAR(3)부터 실제 클리어.
  return (prevClear == null || prevClear < 3) && (newClear != null && newClear >= 3);
}

function buildMergedCourses(data: ScoreUpdatesResponse): MergedCourseUpdate[] {
  const map = new Map<string, MergedCourseUpdate>();

  function getOrCreateCourse(item: ScoreUpdateBase): MergedCourseUpdate {
    const key = `${item.course_name}_${item.client_type}`;
    if (!map.has(key)) {
      map.set(key, {
        course_name: item.course_name,
        dan_title: item.dan_title,
        client_type: item.client_type,
        recorded_at: item.recorded_at,
        currentClearType: item.current_state?.clear_type ?? null,
        currentState: item.current_state ?? null,
        options: item.options,
      });
    }
    return map.get(key)!;
  }

  for (const item of data.clear_type_updates) {
    if (!item.is_course) continue;
    getOrCreateCourse(item).clear = { prev: item.prev_clear_type, new: item.new_clear_type };
  }
  for (const item of data.exscore_updates) {
    if (!item.is_course) continue;
    const entry = getOrCreateCourse(item);
    entry.score = { prev: item.prev_exscore, new: item.new_exscore, prev_rank: item.prev_rank, new_rank: item.new_rank };
    entry.rate = { prev: item.prev_rate, new: item.new_rate };
  }
  for (const item of data.play_count_updates) {
    if (!item.is_course) continue;
    getOrCreateCourse(item).playCount = { prev: item.prev_play_count, new: item.new_play_count };
  }
  return Array.from(map.values());
}

function CourseSectionTable({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  const thCls = "px-2 py-2 font-medium whitespace-nowrap text-left";
  return (
    <div className="border border-border/40 rounded-lg overflow-hidden">
      <div className="px-3 py-2 bg-muted/30 border-b border-border/40">
        <p className="text-body font-semibold text-foreground">
          {title}{" "}
          <span className="text-muted-foreground font-normal text-label">({count})</span>
        </p>
      </div>
      <div className="overflow-auto">
        <table className="w-full text-label" style={{ minWidth: "780px" }}>
          <colgroup>
            <col style={{ width: "110px" }} />
            <col style={{ width: "130px" }} />
            <col />
            <col style={{ width: "80px" }} />
            <col style={{ width: "100px" }} />
            <col style={{ width: "75px" }} />
            <col style={{ width: "105px" }} />
            <col style={{ width: "75px" }} />
            <col style={{ width: "50px" }} />
            <col style={{ width: "45px" }} />
          </colgroup>
          <thead className="sticky top-0 z-10 bg-background text-foreground border-b border-border/50">
            <tr>
              <th className={cn(thCls, "text-center")}>이전</th>
              <th className={cn(thCls, "text-center")}>현재</th>
              <th className={thCls}>코스</th>
              <th className={cn(thCls, "text-center")}>BP</th>
              <th className={cn(thCls, "text-center")}>판정</th>
              <th className={cn(thCls, "text-center")}>랭크</th>
              <th className={cn(thCls, "text-center")}>점수</th>
              <th className={cn(thCls, "text-center")}>플레이 수</th>
              <th className={thCls}>배치</th>
              <th className={thCls}>구동기</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/20">{children}</tbody>
        </table>
      </div>
    </div>
  );
}

function CourseTableRow({ item }: { item: MergedCourseUpdate }) {
  const newClearCls = item.clear ? clearTdClass(item.clear.new) : "";

  const isPlayOnly = !item.clear && !item.score;
  const playOnlyCt = isPlayOnly ? (item.currentClearType ?? null) : null;
  const playOnlyClearCls = isPlayOnly ? clearTdClass(playOnlyCt) : "";
  const rowColorCls = item.clear ? newClearCls : isPlayOnly ? playOnlyClearCls : "";

  // BP — currentState 그대로 표시 (퓨먼과 동일)
  const bp = item.currentState?.min_bp ?? null;

  // Rate — FumenRow와 동일 패턴: rate 전용 필드 우선, 없으면 currentState 폴백
  const rateVal = item.currentState?.rate ?? null;
  const rateLabel = rateVal != null ? `${rateVal.toFixed(1)}%` : null;

  // Rank — FumenRow와 동일 패턴
  const rankNew = item.score?.new_rank ?? item.currentState?.rank ?? null;
  const rankPrev = item.score?.prev_rank ?? null;

  // Score — FumenRow와 동일 패턴
  const scoreNew = item.score?.new ?? item.currentState?.exscore ?? null;
  const scorePrev = item.score?.prev ?? null;
  const scoreDiff = scoreNew != null && scorePrev != null ? scoreNew - scorePrev : null;

  // Plays
  const playsNew = item.playCount?.new ?? null;
  const playsPrev = item.playCount?.prev ?? null;
  const playsDiff = playsNew != null && playsPrev != null ? playsNew - playsPrev : null;

  // Option / Env
  const arrangementName = parseArrangement(item.options ?? null, item.client_type);
  const optionLabel = arrangementName ? (ARRANGEMENT_KANJI[arrangementName] ?? arrangementName) : null;
  const envLabel = item.client_type === "lr2" ? "LR" : item.client_type === "beatoraja" ? "BR" : item.client_type;

  return (
    <tr>
      {/* Prev */}
      <td className={cn(
        "px-2 py-2 whitespace-nowrap text-center",
        item.clear ? clearTdClass(item.clear.prev, true)
          : isPlayOnly ? clearTdClass(playOnlyCt, true)
          : "",
      )}>
        {item.clear ? (
          <span className="text-label opacity-80">
            {CLEAR_TYPE_LABELS_SIMPLE[item.clear.prev ?? 0] ?? "?"}
          </span>
        ) : isPlayOnly ? (
          <span className="text-label opacity-80">
            {CLEAR_TYPE_LABELS_SIMPLE[playOnlyCt ?? 0] ?? "?"}
          </span>
        ) : (
          <span className="text-label row-muted">—</span>
        )}
      </td>

      {/* Current */}
      <td className={cn("px-2 py-2 whitespace-nowrap text-center", item.clear ? newClearCls : isPlayOnly ? playOnlyClearCls : "")}>
        {item.clear ? (
          <span className="text-label font-semibold">
            {clearText(item.clear.new, item.client_type)}
          </span>
        ) : isPlayOnly ? (
          <span className="text-label font-semibold">
            {clearText(playOnlyCt, item.client_type)}
          </span>
        ) : (
          <span className="row-muted">—</span>
        )}
      </td>

      {/* Course name — Prev/Current 바로 다음 */}
      <td className={cn("px-2 py-2", rowColorCls)}>
        <div className="flex items-center gap-1.5 flex-wrap min-w-0">
          {item.dan_title && (
            <span className="text-label font-bold text-accent shrink-0">{item.dan_title}</span>
          )}
          <span className="text-label font-medium truncate">
            {item.course_name ?? "(코스 불명)"}
          </span>
        </div>
      </td>

      {/* BP */}
      <td className={cn("px-2 py-2 whitespace-nowrap text-center", rowColorCls)}>
        {bp != null ? <span className="text-label">{bp}</span> : <span className="row-muted">—</span>}
      </td>

      {/* Rate — FumenRow와 동일 패턴 */}
      <td className={cn("px-2 py-2 whitespace-nowrap text-center", rowColorCls)}>
        {item.rate?.prev != null ? (
          <div className="flex items-baseline gap-1 justify-center">
            <span className="text-label opacity-70">{item.rate.prev.toFixed(1)}% →</span>
            <span className="text-label font-semibold">{item.rate.new?.toFixed(1) ?? "?"}%</span>
            {item.rate.new != null && item.rate.prev != null && item.rate.new - item.rate.prev > 0 && (
              <span className="text-label font-bold opacity-75">▲{(item.rate.new - item.rate.prev).toFixed(1)}</span>
            )}
          </div>
        ) : item.rate?.new != null ? (
          <span className="text-label">{item.rate.new.toFixed(1)}%</span>
        ) : rateLabel ? (
          <span className="text-label">{rateLabel}</span>
        ) : <span className="row-muted">—</span>}
      </td>

      {/* Rank */}
      <td className={cn("px-2 py-2 whitespace-nowrap text-center", rowColorCls)}>
        {item.score?.new_rank ? (
          rankPrev ? (
            <span className="text-label">
              <span className="opacity-70">{rankPrev} → </span>
              <span className="font-semibold">{item.score.new_rank}</span>
            </span>
          ) : (
            <span className="text-label">{item.score.new_rank}</span>
          )
        ) : rankNew ? (
          <span className="text-label">{rankNew}</span>
        ) : <span className="row-muted">—</span>}
      </td>

      {/* Score */}
      <td className={cn("px-2 py-2 whitespace-nowrap text-center", rowColorCls)}>
        {item.score?.prev != null ? (
          <div className="flex items-baseline gap-1 justify-center">
            <span className="text-label opacity-70">{item.score.prev} →</span>
            <span className="text-label font-semibold">{item.score.new ?? "–"}</span>
            {scoreDiff != null && scoreDiff > 0 && (
              <span className="text-label font-bold opacity-75">▲{scoreDiff}</span>
            )}
          </div>
        ) : item.score?.new != null ? (
          <span className="text-label">{item.score.new}</span>
        ) : scoreNew != null ? (
          <span className="text-label">{scoreNew}</span>
        ) : <span className="row-muted">—</span>}
      </td>

      {/* Plays */}
      <td className={cn("px-2 py-2 whitespace-nowrap text-center", rowColorCls)}>
        {item.playCount?.prev != null ? (
          <div className="flex items-baseline gap-1 justify-center">
            <span className="text-label opacity-70">{item.playCount.prev} →</span>
            <span className="text-label font-semibold">{item.playCount.new ?? "–"}</span>
            {playsDiff != null && playsDiff > 0 && (
              <span className="text-label font-bold opacity-75">▲{playsDiff}</span>
            )}
          </div>
        ) : item.playCount?.new != null ? (
          <span className="text-label">{item.playCount.new}</span>
        ) : <span className="row-muted">—</span>}
      </td>

      {/* Option */}
      <td className={cn("px-2 py-2 text-label", rowColorCls)}>
        {optionLabel ?? <span className="row-muted">—</span>}
      </td>

      {/* Env */}
      <td className={cn("px-2 py-2 text-label", rowColorCls)}>
        {envLabel}
      </td>
    </tr>
  );
}

// ── Shared section table wrapper ───────────────────────────────────────────────

const handleSectionTableCopy = makeTableCopyHandler(3, "tbody tr"); // col 0=Prev, 1=Current, 2=Level, 3=Title/Artist
const handleFumenTableCopy = makeTableCopyHandler(1, "tbody tr");   // col 0=Level, 1=Title/Artist

function SectionTable({
  title,
  count,
  showNewPlays,
  onToggleNewPlays,
  colWidths = ["110px", "120px", "100px", undefined],
  children,
}: {
  title: string;
  count: number;
  showNewPlays?: boolean;
  onToggleNewPlays?: () => void;
  /** [Prev, Current, Level, Title] — undefined = auto */
  colWidths?: [string?, string?, string?, string?];
  children: React.ReactNode;
}) {
  const thCls = "px-2 py-2 font-medium whitespace-nowrap text-left";
  return (
    <div className="border border-border/40 rounded-lg overflow-hidden">
      <div className="px-3 py-2 bg-muted/30 border-b border-border/40 flex items-center justify-between gap-2">
        <p className="text-body font-semibold text-foreground">
          {title}{" "}
          <span className="text-muted-foreground font-normal text-label">({count})</span>
        </p>
        {onToggleNewPlays !== undefined && (
          <label className="flex items-center gap-1.5 cursor-pointer text-label text-muted-foreground select-none shrink-0">
            <input
              type="checkbox"
              checked={showNewPlays ?? true}
              onChange={onToggleNewPlays}
              className="accent-primary"
            />
            신규 기록 포함
          </label>
        )}
      </div>
      <div className="overflow-auto">
        <table className="w-full table-fixed text-label" onCopy={handleSectionTableCopy}>
          <colgroup>
            {colWidths.map((w, i) => (
              <col key={i} style={w ? { width: w } : undefined} />
            ))}
          </colgroup>
          <thead className="sticky top-0 z-10 bg-background text-foreground border-b border-border/50">
            <tr>
              <th className={cn(thCls, "text-center")}>이전</th>
              <th className={cn(thCls, "text-center")}>현재</th>
              <th className={thCls}>레벨</th>
              <th className={thCls}>제목</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/20">{children}</tbody>
        </table>
      </div>
    </div>
  );
}

// ── Category tab row components ────────────────────────────────────────────────

function LampUpgradeRow({ item }: { item: ClearTypeUpdateItem }) {
  const newCls = clearTdClass(item.new_clear_type);
  return (
    <tr>
      <td className={cn("px-2 py-2 whitespace-nowrap text-center", clearTdClass(item.prev_clear_type, true))}>
        <span className="text-label opacity-80">
          {CLEAR_TYPE_LABELS_SIMPLE[item.prev_clear_type ?? 0] ?? "?"}
        </span>
      </td>
      <td className={cn("px-2 py-2 whitespace-nowrap text-center font-semibold", newCls)}>
        {clearText(item.new_clear_type, item.client_type)}
      </td>
      <td className={cn("px-2 py-2", newCls)}>
        <TableLevelBadges levels={item.table_levels} />
      </td>
      <td className={cn("px-2 py-2", newCls)} data-title={item.title ?? ""} data-artist={item.artist ?? ""}>
        <div className="max-w-full truncate">
          {(item.fumen_sha256 || item.fumen_md5) ? (
            <Link
              href={`/songs/${item.fumen_sha256 || item.fumen_md5}`}
              className="text-label hover:text-primary transition-colors"
            >
              {item.title ?? "(알 수 없음)"}
            </Link>
          ) : (
            <span className="text-label">{item.title ?? "(알 수 없음)"}</span>
          )}
        </div>
        {item.artist && <div className="text-caption max-w-full truncate opacity-70">{item.artist}</div>}
      </td>
    </tr>
  );
}


function ScoreUpgradeRow({ item }: { item: ExscoreUpdateItem }) {
  const scoreDiff =
    item.prev_exscore != null && item.new_exscore != null
      ? item.new_exscore - item.prev_exscore
      : null;
  const newCls = rankTdClass(item.new_rank);

  return (
    <tr>
      <td className={cn("px-2 py-2 whitespace-nowrap text-center", rankTdClass(item.prev_rank, true))}>
        {item.prev_rank == null ? (
          <span className="text-label">NO PLAY</span>
        ) : (
          <div className="flex flex-col items-center gap-0.5">
            <span className="text-label">{item.prev_rank}</span>
            <span className="text-label">{item.prev_exscore ?? "–"}</span>
          </div>
        )}
      </td>
      <td className={cn("px-2 py-2 whitespace-nowrap text-center", newCls)}>
        <div className="flex flex-col items-center gap-0.5">
          <span className="text-label font-semibold">{item.new_rank ?? "–"}</span>
          <div className="flex items-baseline gap-1">
            <span className="text-label font-semibold">{item.new_exscore ?? "–"}</span>
            {scoreDiff != null && scoreDiff > 0 && (
              <span className="text-label font-bold opacity-75">▲{scoreDiff}</span>
            )}
          </div>
        </div>
      </td>
      <td className={cn("px-2 py-2", newCls)}>
        <TableLevelBadges levels={item.table_levels} />
      </td>
      <td className={cn("px-2 py-2", newCls)} data-title={item.title ?? ""} data-artist={item.artist ?? ""}>
        <div className="max-w-full truncate">
          {(item.fumen_sha256 || item.fumen_md5) ? (
            <Link
              href={`/songs/${item.fumen_sha256 || item.fumen_md5}`}
              className="text-label hover:text-primary transition-colors"
            >
              {item.title ?? "(알 수 없음)"}
            </Link>
          ) : (
            <span className="text-label">{item.title ?? "(알 수 없음)"}</span>
          )}
        </div>
        {item.artist && <div className="text-caption max-w-full truncate opacity-70">{item.artist}</div>}
      </td>
    </tr>
  );
}

function BPUpgradeRow({ item }: { item: MinBPUpdateItem }) {
  const prev = item.prev_min_bp;
  const next = item.new_min_bp;
  const diff = prev != null && next != null ? prev - next : null;

  return (
    <tr className="transition-all hover:bg-secondary/30">
      <td className="px-2 py-2 whitespace-nowrap text-center">
        <span className="text-label text-muted-foreground/60">
          {prev == null ? "NO PLAY" : prev}
        </span>
      </td>
      <td className="px-2 py-2 whitespace-nowrap text-center">
        <div className="inline-flex items-baseline gap-1.5">
          <span className="text-label font-semibold">{next ?? "–"}</span>
          {diff != null && diff > 0 && (
            <span className="text-label font-bold" style={{ color: "hsl(var(--clear-hard))" }}>
              ▼{diff}
            </span>
          )}
        </div>
      </td>
      <td className="px-2 py-2">
        <TableLevelBadges levels={item.table_levels} />
      </td>
      <td className="px-2 py-2" data-title={item.title ?? ""} data-artist={item.artist ?? ""}>
        <div className="max-w-full truncate">
          {(item.fumen_sha256 || item.fumen_md5) ? (
            <Link
              href={`/songs/${item.fumen_sha256 || item.fumen_md5}`}
              className="text-label hover:text-primary transition-colors"
            >
              {item.title ?? "(알 수 없음)"}
            </Link>
          ) : (
            <span className="text-label">{item.title ?? "(알 수 없음)"}</span>
          )}
        </div>
        {item.artist && <div className="text-caption text-muted-foreground max-w-full truncate opacity-70">{item.artist}</div>}
      </td>
    </tr>
  );
}

function ComboUpgradeRow({ item }: { item: MaxComboUpdateItem }) {
  const prev = item.prev_max_combo;
  const next = item.new_max_combo;
  const diff = prev != null && next != null ? next - prev : null;

  return (
    <tr className="transition-all hover:bg-secondary/30">
      <td className="px-2 py-2 whitespace-nowrap text-center">
        <span className="text-label text-muted-foreground/60">
          {prev == null ? "NO PLAY" : prev}
        </span>
      </td>
      <td className="px-2 py-2 whitespace-nowrap text-center">
        <div className="inline-flex items-baseline gap-1.5">
          <span className="text-label font-semibold">{next ?? "–"}</span>
          {diff != null && diff > 0 && (
            <span className="text-label font-bold" style={{ color: "hsl(var(--clear-fc) / 0.85)" }}>
              ▲{diff}
            </span>
          )}
        </div>
      </td>
      <td className="px-2 py-2">
        <TableLevelBadges levels={item.table_levels} />
      </td>
      <td className="px-2 py-2" data-title={item.title ?? ""} data-artist={item.artist ?? ""}>
        <div className="max-w-full truncate">
          {(item.fumen_sha256 || item.fumen_md5) ? (
            <Link
              href={`/songs/${item.fumen_sha256 || item.fumen_md5}`}
              className="text-label hover:text-primary transition-colors"
            >
              {item.title ?? "(알 수 없음)"}
            </Link>
          ) : (
            <span className="text-label">{item.title ?? "(알 수 없음)"}</span>
          )}
        </div>
        {item.artist && <div className="text-caption text-muted-foreground max-w-full truncate opacity-70">{item.artist}</div>}
      </td>
    </tr>
  );
}

// ── Category tab ───────────────────────────────────────────────────────────────

function CategoryTab({ data }: { data: ScoreUpdatesResponse }) {
  const prefs = useScoreUpdatesPrefs();
  const { mutate: updatePrefs } = useUpdateScoreUpdatesPrefs();

  const mergedCourses = useMemo(() => buildMergedCourses(data), [data]);

  const lampAll = useMemo(() =>
    [...data.clear_type_updates]
      .filter((u) => !u.is_course)
      .sort((a, b) => {
        const ct = (b.new_clear_type ?? 0) - (a.new_clear_type ?? 0);
        return ct !== 0 ? ct : compareByTableLevels(a.table_levels, b.table_levels);
      }),
  [data]);

  const scoreAll = useMemo(() =>
    [...data.exscore_updates]
      .filter((u) => !u.is_course)
      .sort((a, b) => {
        const ra = RANK_SORT_ORDER[a.new_rank ?? "F"] ?? 99;
        const rb = RANK_SORT_ORDER[b.new_rank ?? "F"] ?? 99;
        const rank = ra - rb;
        return rank !== 0 ? rank : compareByTableLevels(a.table_levels, b.table_levels);
      }),
  [data]);

  const bpAll = useMemo(() =>
    [...data.min_bp_updates].sort((a, b) => {
      const aDiff = a.prev_min_bp != null && a.new_min_bp != null ? a.prev_min_bp - a.new_min_bp : -1;
      const bDiff = b.prev_min_bp != null && b.new_min_bp != null ? b.prev_min_bp - b.new_min_bp : -1;
      const diff = bDiff - aDiff;
      return diff !== 0 ? diff : compareByTableLevels(a.table_levels, b.table_levels);
    }),
  [data]);

  const comboAll = useMemo(() =>
    [...data.max_combo_updates].sort((a, b) => {
      const aDiff = a.prev_max_combo != null && a.new_max_combo != null ? a.new_max_combo - a.prev_max_combo : -1;
      const bDiff = b.prev_max_combo != null && b.new_max_combo != null ? b.new_max_combo - b.prev_max_combo : -1;
      const diff = bDiff - aDiff;
      return diff !== 0 ? diff : compareByTableLevels(a.table_levels, b.table_levels);
    }),
  [data]);

  const lamp = useMemo(
    () => prefs.score_updates_lamp_include_new_plays ? lampAll : lampAll.filter((u) => !u.is_new_play),
    [lampAll, prefs.score_updates_lamp_include_new_plays],
  );
  const score = useMemo(
    () => prefs.score_updates_score_include_new_plays ? scoreAll : scoreAll.filter((u) => !u.is_new_play),
    [scoreAll, prefs.score_updates_score_include_new_plays],
  );
  const bp = useMemo(
    () => prefs.score_updates_bp_include_new_plays ? bpAll : bpAll.filter((u) => !u.is_new_play),
    [bpAll, prefs.score_updates_bp_include_new_plays],
  );
  const combo = useMemo(
    () => prefs.score_updates_combo_include_new_plays ? comboAll : comboAll.filter((u) => !u.is_new_play),
    [comboAll, prefs.score_updates_combo_include_new_plays],
  );

  // 요약 탭: 개선된 기록만 표시 (playCount-only 제외)
  const summaryCourses = useMemo(
    () => mergedCourses.filter((c) => c.clear || c.score),
    [mergedCourses],
  );

  const empty =
    summaryCourses.length === 0 &&
    lampAll.length === 0 &&
    scoreAll.length === 0 &&
    bpAll.length === 0 &&
    comboAll.length === 0;

  if (empty) {
    return (
      <p className="text-body text-muted-foreground text-center py-8">
        기록 상세 데이터가 없습니다.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {/* Course records */}
      {summaryCourses.length > 0 && (
        <CourseSectionTable title="코스 기록" count={summaryCourses.length}>
          {summaryCourses.map((c, i) => (
            <CourseTableRow key={i} item={c} />
          ))}
        </CourseSectionTable>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {lampAll.length > 0 && (
          <SectionTable
            title="클리어 갱신"
            count={lamp.length}
            showNewPlays={prefs.score_updates_lamp_include_new_plays}
            onToggleNewPlays={() => updatePrefs({ score_updates_lamp_include_new_plays: !prefs.score_updates_lamp_include_new_plays })}
          >
            {lamp.map((item, i) => <LampUpgradeRow key={i} item={item} />)}
          </SectionTable>
        )}
        {scoreAll.length > 0 && (
          <SectionTable
            title="점수 갱신"
            count={score.length}
            showNewPlays={prefs.score_updates_score_include_new_plays}
            onToggleNewPlays={() => updatePrefs({ score_updates_score_include_new_plays: !prefs.score_updates_score_include_new_plays })}
          >
            {score.map((item, i) => <ScoreUpgradeRow key={i} item={item} />)}
          </SectionTable>
        )}
        {bpAll.length > 0 && (
          <SectionTable
            title="BP 갱신"
            count={bp.length}
            showNewPlays={prefs.score_updates_bp_include_new_plays}
            onToggleNewPlays={() => updatePrefs({ score_updates_bp_include_new_plays: !prefs.score_updates_bp_include_new_plays })}
          >
            {bp.map((item, i) => <BPUpgradeRow key={i} item={item} />)}
          </SectionTable>
        )}
        {comboAll.length > 0 && (
          <SectionTable
            title="최대 콤보 갱신"
            count={combo.length}
            showNewPlays={prefs.score_updates_combo_include_new_plays}
            onToggleNewPlays={() => updatePrefs({ score_updates_combo_include_new_plays: !prefs.score_updates_combo_include_new_plays })}
          >
            {combo.map((item, i) => <ComboUpgradeRow key={i} item={item} />)}
          </SectionTable>
        )}
      </div>
    </div>
  );
}

// ── Fumen tab ──────────────────────────────────────────────────────────────────

interface MergedFumenUpdate {
  sha256: string | null;
  md5: string | null;
  title: string | null;
  artist: string | null;
  table_levels: TableLevelRef[];
  client_type: string;
  source_client?: string | null;
  source_client_detail?: Record<string, string | null> | null;
  recorded_at: string | null;
  options: Record<string, unknown> | null;
  clear?: { prev: number | null; new: number | null };
  score?: { prev: number | null; new: number | null; prev_rank: string | null; new_rank: string | null };
  rate?: { prev: number | null; new: number | null };
  bp?: { prev: number | null; new: number | null };
  combo?: { prev: number | null; new: number | null };
  playCount?: { prev: number | null; new: number | null };
  currentState?: {
    clear_type: number | null;
    exscore: number | null;
    rate: number | null;
    rank: string | null;
    min_bp: number | null;
    max_combo: number | null;
  };
}

function buildMergedFumens(data: ScoreUpdatesResponse): MergedFumenUpdate[] {
  const map = new Map<string, MergedFumenUpdate>();

  function getOrCreate(
    sha256: string | null,
    md5: string | null,
    title: string | null,
    artist: string | null,
    table_levels: TableLevelRef[],
    client_type: string,
    recorded_at: string | null,
    options: Record<string, unknown> | null,
    source_client?: string | null,
    source_client_detail?: Record<string, string | null> | null,
    currentState?: MergedFumenUpdate["currentState"],
  ): MergedFumenUpdate {
    const key = sha256 ?? md5 ?? `unknown-${Math.random()}`;
    if (!map.has(key)) {
      map.set(key, {
        sha256,
        md5,
        title,
        artist,
        table_levels,
        client_type,
        source_client,
        source_client_detail,
        recorded_at,
        options,
        currentState,
      });
    }
    return map.get(key)!;
  }

  for (const item of data.clear_type_updates) {
    if (item.is_course) continue;
    const entry = getOrCreate(item.fumen_sha256, item.fumen_md5, item.title, item.artist, item.table_levels, item.client_type, item.recorded_at, item.options, item.source_client, item.source_client_detail, item.current_state);
    entry.clear = { prev: item.prev_clear_type, new: item.new_clear_type };
    if (entry.bp == null && item.best_min_bp != null) {
      entry.bp = { prev: null, new: item.best_min_bp };
    }
  }

  for (const item of data.exscore_updates) {
    if (item.is_course) continue;
    const entry = getOrCreate(item.fumen_sha256, item.fumen_md5, item.title, item.artist, item.table_levels, item.client_type, item.recorded_at, item.options, item.source_client, item.source_client_detail, item.current_state);
    entry.score = { prev: item.prev_exscore, new: item.new_exscore, prev_rank: item.prev_rank, new_rank: item.new_rank };
    entry.rate = { prev: item.prev_rate, new: item.new_rate };
    if (entry.bp == null && item.best_min_bp != null) {
      entry.bp = { prev: null, new: item.best_min_bp };
    }
  }

  for (const item of data.min_bp_updates) {
    const entry = getOrCreate(item.fumen_sha256, item.fumen_md5, item.title, item.artist, item.table_levels, item.client_type, item.recorded_at, item.options, item.source_client, item.source_client_detail, item.current_state);
    entry.bp = { prev: item.prev_min_bp, new: item.new_min_bp };
  }

  for (const item of data.max_combo_updates) {
    const entry = getOrCreate(item.fumen_sha256, item.fumen_md5, item.title, item.artist, item.table_levels, item.client_type, item.recorded_at, item.options, item.source_client, item.source_client_detail, item.current_state);
    entry.combo = { prev: item.prev_max_combo, new: item.new_max_combo };
  }

  for (const item of data.play_count_updates) {
    if (item.is_course) continue;
    const entry = getOrCreate(item.fumen_sha256, item.fumen_md5, item.title, item.artist, item.table_levels, item.client_type, item.recorded_at, item.options, item.source_client, item.source_client_detail, item.current_state);
    entry.playCount = { prev: item.prev_play_count, new: item.new_play_count };
  }

  return Array.from(map.values()).filter((f) => f.clear || f.score || f.bp || f.combo || f.playCount);
}

function FumenRow({ fumen }: { fumen: MergedFumenUpdate }) {
  const displayClearType = fumen.clear?.new ?? fumen.currentState?.clear_type ?? null;
  const rowClass = displayClearType != null ? (CLEAR_ROW_CLASS[displayClearType] ?? "") : "";

  const scoreDiff =
    fumen.score?.prev != null && fumen.score?.new != null
      ? fumen.score.new - fumen.score.prev
      : null;

  const arrangementName = parseArrangement(fumen.options, fumen.client_type);
  const optionLabel = arrangementName ? (ARRANGEMENT_KANJI[arrangementName] ?? arrangementName) : null;

  const rate = fumen.currentState?.rate;
  const rateLabel = rate != null ? `${rate.toFixed(1)}%` : null;

  return (
    <tr className={cn("transition-all", rowClass || "hover:bg-secondary/50")}>
      {/* Level */}
      <td className="px-2 py-2 align-top">
        <TableLevelBadges levels={fumen.table_levels} />
      </td>

      {/* Title + Artist */}
      <td className="px-2 py-2 align-top max-w-[220px]" data-title={fumen.title ?? ""} data-artist={fumen.artist ?? ""}>
        {(fumen.sha256 || fumen.md5) ? (
          <Link
            href={`/songs/${fumen.sha256 || fumen.md5}`}
            className="text-label inline-block max-w-full truncate hover:text-primary transition-colors"
          >
            {fumen.title ?? "(알 수 없음)"}
          </Link>
        ) : (
          <span className="text-label inline-block max-w-full truncate">{fumen.title ?? "(알 수 없음)"}</span>
        )}
        {fumen.artist && <><br /><span className="text-caption row-muted inline-block max-w-full truncate">{fumen.artist}</span></>}
      </td>

      {/* Lamp */}
      <td className="px-2 py-2 align-top text-label whitespace-nowrap text-center">
        {fumen.clear ? (
          <span>
            <span className="opacity-70">{CLEAR_TYPE_LABELS_SIMPLE[fumen.clear.prev ?? 0] ?? "?"}</span>
            <span className="opacity-70"> → </span>
            <span className="font-semibold">{clearText(fumen.clear.new, fumen.client_type)}</span>
          </span>
        ) : fumen.currentState?.clear_type != null ? (
          clearText(fumen.currentState.clear_type, fumen.client_type)
        ) : (
          <span className="row-muted">—</span>
        )}
      </td>

      {/* BP */}
      <td className="px-2 py-2 align-top text-label whitespace-nowrap text-center">
        {fumen.bp?.prev != null ? (
          <span>
            <span className="opacity-70">{fumen.bp.prev} →</span>
            <span className="font-semibold">{fumen.bp.new ?? "?"}</span>
            {fumen.bp.new != null && fumen.bp.prev - fumen.bp.new > 0 && (
              <span className="text-label font-bold opacity-75"> ▼{fumen.bp.prev - fumen.bp.new}</span>
            )}
          </span>
        ) : fumen.bp?.new != null ? (
          <span>{fumen.bp.new}</span>
        ) : fumen.currentState?.min_bp != null ? (
          <span>{fumen.currentState.min_bp}</span>
        ) : (
          <span className="row-muted">—</span>
        )}
      </td>

      {/* Rate */}
      <td className="px-2 py-2 align-top text-label whitespace-nowrap text-center">
        {fumen.rate?.prev != null ? (
          <span>
            <span className="opacity-70">{fumen.rate.prev.toFixed(1)}% →</span>
            <span className="font-semibold">{fumen.rate.new?.toFixed(1) ?? "?"}%</span>
            {fumen.rate.new != null && fumen.rate.new - fumen.rate.prev > 0 && (
              <span className="text-label font-bold opacity-75"> ▲{(fumen.rate.new - fumen.rate.prev).toFixed(1)}</span>
            )}
          </span>
        ) : fumen.rate?.new != null ? (
          <span>{fumen.rate.new.toFixed(1)}%</span>
        ) : rateLabel ? (
          <span>{rateLabel}</span>
        ) : (
          <span className="row-muted">—</span>
        )}
      </td>

      {/* Rank */}
      <td className="px-2 py-2 align-top text-label whitespace-nowrap text-center">
        {fumen.score?.new_rank ? (
          fumen.score.prev_rank ? (
            <span>
              <span className="opacity-70">{fumen.score.prev_rank} → </span>
              <span className="font-semibold">{fumen.score.new_rank}</span>
            </span>
          ) : (
            <span>{fumen.score.new_rank}</span>
          )
        ) : fumen.currentState?.rank ? (
          <span>{fumen.currentState.rank}</span>
        ) : (
          <span className="row-muted">—</span>
        )}
      </td>

      {/* Score */}
      <td className="px-2 py-2 align-top text-label whitespace-nowrap text-center">
        {fumen.score?.prev != null ? (
          <span>
            <span className="opacity-70">{fumen.score.prev} →</span>
            <span className="font-semibold">{fumen.score.new ?? "–"}</span>
            {scoreDiff != null && scoreDiff > 0 && (
              <span className="text-label font-bold opacity-75"> ▲{scoreDiff}</span>
            )}
          </span>
        ) : fumen.score?.new != null ? (
          <span>{fumen.score.new}</span>
        ) : fumen.currentState?.exscore != null ? (
          <span>{fumen.currentState.exscore}</span>
        ) : (
          <span className="row-muted">—</span>
        )}
      </td>

      {/* Plays */}
      <td className="px-2 py-2 align-top text-label whitespace-nowrap text-center">
        {fumen.playCount?.prev != null ? (
          <span>
            <span className="opacity-70">{fumen.playCount.prev} →</span>
            <span className="font-semibold">{fumen.playCount.new ?? "–"}</span>
            {fumen.playCount.new != null && fumen.playCount.new - fumen.playCount.prev > 0 && (
              <span className="text-label font-bold opacity-75"> ▲{fumen.playCount.new - fumen.playCount.prev}</span>
            )}
          </span>
        ) : fumen.playCount?.new != null ? (
          <span>{fumen.playCount.new}</span>
        ) : (
          <span className="row-muted">—</span>
        )}
      </td>

      {/* Option */}
      <td className="px-2 py-2 align-top text-label">
        {optionLabel ? (
          <span>{optionLabel}</span>
        ) : (
          <span className="row-muted">—</span>
        )}
      </td>

      {/* Env (client) */}
      <td className="px-2 py-2 align-top text-label">
        <SourceClientBadge
          sourceClient={fumen.source_client}
          sourceClientDetail={fumen.source_client_detail}
          fallbackClientTypes={[fumen.client_type]}
        />
      </td>
    </tr>
  );
}

type FumenSortKey = "recorded_at" | "level" | "title" | "lamp" | "score" | "bp" | "rate" | "rank" | "plays" | "option" | "env";

function FumenTab({ data }: { data: ScoreUpdatesResponse }) {
  const [sortKey, setSortKey] = useState<FumenSortKey>("level");
  const [sortAsc, setSortAsc] = useState(true);

  const baseFumens = useMemo(() => buildMergedFumens(data), [data]);
  const mergedCourses = useMemo(() => buildMergedCourses(data), [data]);

  const fumens = useMemo(() => {
    const sorted = [...baseFumens].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "recorded_at":
          cmp = (a.recorded_at ?? "").localeCompare(b.recorded_at ?? "");
          break;
        case "level":
          cmp = compareByTableLevels(a.table_levels, b.table_levels);
          break;
        case "title":
          cmp = compareTitles(a.title ?? "", b.title ?? "");
          break;
        case "lamp":
          cmp = ((a.clear?.new ?? a.currentState?.clear_type ?? -1)) - ((b.clear?.new ?? b.currentState?.clear_type ?? -1));
          break;
        case "score":
          cmp = ((a.score?.new ?? a.currentState?.exscore ?? -1)) - ((b.score?.new ?? b.currentState?.exscore ?? -1));
          break;
        case "bp":
          cmp = ((a.currentState?.min_bp ?? 99999)) - ((b.currentState?.min_bp ?? 99999));
          break;
        case "rank": {
          const ra = RANK_SORT_ORDER[a.score?.new_rank ?? a.currentState?.rank ?? "F"] ?? 99;
          const rb = RANK_SORT_ORDER[b.score?.new_rank ?? b.currentState?.rank ?? "F"] ?? 99;
          cmp = ra - rb;
          break;
        }
        case "rate":
          cmp = (a.currentState?.rate ?? -1) - (b.currentState?.rate ?? -1);
          break;
        case "plays":
          cmp = (a.playCount?.new ?? -1) - (b.playCount?.new ?? -1);
          break;
        case "option":
          cmp = (parseArrangement(a.options, a.client_type) ?? "").localeCompare(
            parseArrangement(b.options, b.client_type) ?? ""
          );
          break;
        case "env":
          cmp = (a.source_client ?? a.client_type).localeCompare(b.source_client ?? b.client_type);
          break;
      }
      return sortAsc ? cmp : -cmp;
    });
    return sorted;
  }, [baseFumens, sortKey, sortAsc]);

  const toggleSort = (key: FumenSortKey) => {
    if (sortKey === key) setSortAsc((v: boolean) => !v);
    else { setSortKey(key); setSortAsc(false); }
  };

  const thClass = (key: FumenSortKey, center = false) =>
    cn(
      "px-2 py-2 font-medium select-none whitespace-nowrap cursor-pointer hover:text-foreground transition-colors",
      center ? "text-center" : "text-left",
    );

  const sortIcon = (colKey: FumenSortKey) => {
    if (sortKey === colKey) {
      return <span className="ml-1">{sortAsc ? "↑" : "↓"}</span>;
    }
    return <span className="ml-1 text-muted-foreground/35">⇅</span>;
  };

  const empty = mergedCourses.length === 0 && fumens.length === 0;

  if (empty) {
    return (
      <p className="text-body text-muted-foreground text-center py-8">
        기록 상세 데이터가 없습니다.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {mergedCourses.length > 0 && (
        <CourseSectionTable title="코스 기록" count={mergedCourses.length}>
          {mergedCourses.map((c, i) => (
            <CourseTableRow key={i} item={c} />
          ))}
        </CourseSectionTable>
      )}

      {fumens.length > 0 && (
        <div className="border border-border/40 rounded-lg overflow-hidden">
          <div className="overflow-auto max-h-[480px]">
            <table className="w-full text-label min-w-[760px]" onCopy={handleFumenTableCopy}>
              <colgroup>
                <col style={{ width: "100px" }} />
                <col />
                <col style={{ width: "140px" }} />
                <col style={{ width: "100px" }} />
                <col style={{ width: "120px" }} />
                <col style={{ width: "90px" }} />
                <col style={{ width: "120px" }} />
                <col style={{ width: "90px" }} />
                <col style={{ width: "50px" }} />
                <col style={{ width: "50px" }} />
              </colgroup>
              <thead className="sticky top-0 z-10 bg-background text-foreground border-b border-border/50">
                <tr>
                  <th className={thClass("level")} onClick={() => toggleSort("level")}>레벨{sortIcon("level")}</th>
                  <th className={thClass("title")} onClick={() => toggleSort("title")}>제목{sortIcon("title")}</th>
                  <th className={thClass("lamp", true)} onClick={() => toggleSort("lamp")}>클리어{sortIcon("lamp")}</th>
                  <th className={thClass("bp", true)} onClick={() => toggleSort("bp")}>BP{sortIcon("bp")}</th>
                  <th className={thClass("rate", true)} onClick={() => toggleSort("rate")}>판정{sortIcon("rate")}</th>
                  <th className={thClass("rank", true)} onClick={() => toggleSort("rank")}>랭크{sortIcon("rank")}</th>
                  <th className={thClass("score", true)} onClick={() => toggleSort("score")}>점수{sortIcon("score")}</th>
                  <th className={thClass("plays", true)} onClick={() => toggleSort("plays")}>플레이 수{sortIcon("plays")}</th>
                  <th className={thClass("option")} onClick={() => toggleSort("option")}>배치{sortIcon("option")}</th>
                  <th className={thClass("env")} onClick={() => toggleSort("env")}>구동기{sortIcon("env")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/30">
                {fumens.map((fumen, i) => (
                  <FumenRow key={fumen.sha256 ?? fumen.md5 ?? i} fumen={fumen} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

interface ScoreUpdatesProps {
  clientType?: ClientTypeFilter;
  date?: string;
  limit?: number;
  ratingSlot?: React.ReactNode;
  ratingBadgeCount?: number;
  userId?: string;
}

export function ScoreUpdates({
  clientType,
  date,
  limit = 50,
  ratingSlot,
  ratingBadgeCount = 0,
  userId,
}: ScoreUpdatesProps) {
  const { data, isLoading } = useScoreUpdates(clientType, date, limit, userId);
  const [viewMode, setViewMode] = useState<"summary" | "rating" | "all">("summary");

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle>기록 상세</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="h-4 w-32 bg-muted rounded animate-pulse" />
                <div className="h-4 w-16 bg-muted rounded animate-pulse" />
              </div>
            ))}
          </div>
        )}

        {!isLoading && data && (
          <Tabs
            value={viewMode}
            onValueChange={(v) => setViewMode(v as "summary" | "rating" | "all")}
          >
            <div className="flex justify-center mb-4">
              <TabsList>
                <TabsTrigger value="summary">갱신 요약</TabsTrigger>
                {ratingSlot !== undefined && (
                  <TabsTrigger value="rating">
                    레이팅 변동
                    {ratingBadgeCount > 0 && (
                      <span className="ml-1.5 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-primary/20 px-1.5 text-caption font-semibold text-primary">
                        {ratingBadgeCount}
                      </span>
                    )}
                  </TabsTrigger>
                )}
                <TabsTrigger value="all">전체</TabsTrigger>
              </TabsList>
            </div>
            <TabsContent value="summary">
              <CategoryTab data={data} />
            </TabsContent>
            {ratingSlot !== undefined && (
              <TabsContent value="rating">{ratingSlot}</TabsContent>
            )}
            <TabsContent value="all">
              <FumenTab data={data} />
            </TabsContent>
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}
