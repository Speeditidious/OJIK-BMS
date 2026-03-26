"use client";

import React, { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  ScoreUpdatesResponse,
  ClearTypeUpdateItem,
  ExscoreUpdateItem,
  MaxComboUpdateItem,
  MinBPUpdateItem,
  TableLevelRef,
} from "@/types";
import { clearBadge } from "@/components/dashboard/RecentActivity";
import type { ClientTypeFilter } from "@/hooks/use-analysis";
import { useScoreUpdates } from "@/hooks/use-analysis";

// ── Helpers ───────────────────────────────────────────────────────────────────

const CLEAR_TYPE_LABELS_SIMPLE: Record<number, string> = {
  0: "NO PLAY", 1: "FAILED", 2: "ASSIST", 3: "EASY", 4: "NORMAL",
  5: "HARD", 6: "EX HARD", 7: "FULL COMBO", 8: "PERFECT", 9: "MAX",
};

const CLEAR_TYPE_VAR: Record<number, string> = {
  0: "no-play", 1: "failed", 2: "assist", 3: "easy", 4: "normal",
  5: "hard", 6: "exhard", 7: "fc", 8: "perfect", 9: "max",
};

// Row background tint by internal clear type (FumenTab only)
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

// Rank color styles for Score section (전, 은, 동 + clear type 계열)
const RANK_COLOR_STYLE: Record<string, React.CSSProperties> = {
  MAX: { color: "hsl(330 65% 78%)", background: "hsl(330 65% 78% / 0.18)", borderLeft: "2px solid hsl(330 65% 78% / 0.5)" },
  AAA: { color: "hsl(46 80% 60%)",  background: "hsl(46 80% 60% / 0.18)",  borderLeft: "2px solid hsl(46 80% 60% / 0.5)" },
  AA:  { color: "hsl(220 15% 72%)", background: "hsl(220 15% 72% / 0.18)", borderLeft: "2px solid hsl(220 15% 72% / 0.5)" },
  A:   { color: "hsl(27 65% 55%)",  background: "hsl(27 65% 55% / 0.18)",  borderLeft: "2px solid hsl(27 65% 55% / 0.5)" },
  B:   { color: "hsl(var(--clear-normal))", background: "hsl(var(--clear-normal) / 0.15)", borderLeft: "2px solid hsl(var(--clear-normal) / 0.4)" },
  C:   { color: "hsl(var(--clear-easy))",   background: "hsl(var(--clear-easy) / 0.15)",   borderLeft: "2px solid hsl(var(--clear-easy) / 0.4)" },
  D:   { color: "hsl(var(--clear-assist))", background: "hsl(var(--clear-assist) / 0.15)", borderLeft: "2px solid hsl(var(--clear-assist) / 0.4)" },
  E:   { color: "hsl(var(--clear-failed))", background: "hsl(var(--clear-failed) / 0.12)", borderLeft: "2px solid hsl(var(--clear-failed) / 0.35)" },
  F:   { color: "hsl(var(--muted-foreground))", background: "hsl(var(--clear-no-play) / 0.5)", borderLeft: "2px solid hsl(var(--muted-foreground) / 0.25)" },
};

const RANK_SORT_ORDER: Record<string, number> = {
  MAX: -1, AAA: 0, AA: 1, A: 2, B: 3, C: 4, D: 5, E: 6, F: 7,
};

// BMS title sort (bms_title_sort.md 규칙)
function charSortGroup(ch: string): number {
  const code = ch.codePointAt(0) ?? 0;
  if (code >= 0x21 && code <= 0x7e) {
    if ((code >= 0x41 && code <= 0x5a) || (code >= 0x61 && code <= 0x7a)) return 1;
    return 0;
  }
  if (code >= 0x3040 && code <= 0x309f) return 3;
  if (code >= 0x30a0 && code <= 0x30ff) return 4;
  if ((code >= 0x4e00 && code <= 0x9fff) || (code >= 0x3400 && code <= 0x4dbf)) return 5;
  return 2;
}

function compareTitles(a: string, b: string): number {
  const ga = charSortGroup([...a][0] ?? "");
  const gb = charSortGroup([...b][0] ?? "");
  if (ga !== gb) return ga - gb;
  return a.localeCompare(b);
}

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

/** 클리어 타입 셀 인라인 스타일 생성. dim=true이면 흐리게 (이전 상태). */
function clearTypeStyle(clearType: number | null, dim = false): React.CSSProperties {
  const varName = CLEAR_TYPE_VAR[clearType ?? 0] ?? "no-play";
  if (dim) {
    return {
      color: `hsl(var(--clear-${varName}) / 0.45)`,
      background: `hsl(var(--clear-${varName}) / 0.06)`,
      borderLeft: `2px solid hsl(var(--clear-${varName}) / 0.18)`,
    };
  }
  return {
    color: `hsl(var(--clear-${varName}))`,
    background: `hsl(var(--clear-${varName}) / 0.18)`,
    borderLeft: `2px solid hsl(var(--clear-${varName}) / 0.5)`,
  };
}

function TableLevelBadges({ levels }: { levels: TableLevelRef[] }) {
  if (levels.length === 0) return <span className="text-xs text-muted-foreground">-</span>;
  const visible = levels.slice(0, 3);
  const rest = levels.length - visible.length;
  return (
    <div className="flex gap-1 flex-wrap">
      {visible.map(({ symbol, level }, i) => (
        <span
          key={i}
          className="inline-flex items-center rounded px-1.5 py-0 text-[10px] font-medium border border-primary/40 text-primary bg-primary/10"
        >
          {symbol}{level}
        </span>
      ))}
      {rest > 0 && (
        <span className="text-[10px] text-muted-foreground">+{rest}</span>
      )}
    </div>
  );
}

function formatTs(ts: string | null): string {
  if (!ts) return "";
  const d = new Date(ts);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

// ── Merged course update (clear + score in one row) ────────────────────────────

interface MergedCourseUpdate {
  course_name: string | null;
  dan_title: string | null;
  client_type: string;
  recorded_at: string | null;
  clear?: { prev: number | null; new: number | null };
  score?: { prev: number | null; new: number | null; prev_rank: string | null; new_rank: string | null };
}

function buildMergedCourses(data: ScoreUpdatesResponse): MergedCourseUpdate[] {
  const map = new Map<string, MergedCourseUpdate>();
  for (const item of data.clear_type_updates) {
    if (!item.is_course) continue;
    const key = `${item.course_name}_${item.client_type}`;
    if (!map.has(key)) map.set(key, { course_name: item.course_name, dan_title: item.dan_title, client_type: item.client_type, recorded_at: item.recorded_at });
    map.get(key)!.clear = { prev: item.prev_clear_type, new: item.new_clear_type };
  }
  for (const item of data.exscore_updates) {
    if (!item.is_course) continue;
    const key = `${item.course_name}_${item.client_type}`;
    if (!map.has(key)) map.set(key, { course_name: item.course_name, dan_title: item.dan_title, client_type: item.client_type, recorded_at: item.recorded_at });
    map.get(key)!.score = { prev: item.prev_exscore, new: item.new_exscore, prev_rank: item.prev_rank, new_rank: item.new_rank };
  }
  return Array.from(map.values());
}

function CourseUpdateRow({ item }: { item: MergedCourseUpdate }) {
  return (
    <div className="flex items-center gap-3 py-2 border-b border-border/40 last:border-0">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          {item.dan_title && (
            <span className="text-xs font-bold text-accent">{item.dan_title}</span>
          )}
          <span className="text-sm font-medium truncate">
            {item.course_name ?? "(코스 불명)"}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {item.clear && (
          <div className="flex items-center gap-1">
            <span
              className="inline-flex items-center justify-center rounded px-1.5 py-0.5 text-[10px] font-semibold whitespace-nowrap"
              style={clearTypeStyle(item.clear.prev, true)}
            >
              {CLEAR_TYPE_LABELS_SIMPLE[item.clear.prev ?? 0] ?? "?"}
            </span>
            <ChevronRight className="w-3 h-3 text-muted-foreground/35" />
            {clearBadge(item.clear.new, item.client_type)}
          </div>
        )}
        {item.score != null && (
          <span className="text-xs font-mono text-muted-foreground">
            {item.score.prev ?? "–"}{" "}
            <span className="text-foreground font-bold">→ {item.score.new ?? "–"}</span>
          </span>
        )}
        <span className="text-[10px] text-muted-foreground">{formatTs(item.recorded_at)}</span>
      </div>
    </div>
  );
}

// ── Shared section table wrapper ───────────────────────────────────────────────

function SectionTable({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-border/40 rounded-lg overflow-hidden">
      <div className="px-3 py-2 bg-muted/30 border-b border-border/40">
        <p className="text-sm font-semibold text-foreground">
          {title}{" "}
          <span className="text-muted-foreground font-normal text-xs">({count})</span>
        </p>
      </div>
      <div className="overflow-auto">
        <table className="w-full text-xs">
          <tbody className="divide-y divide-border/20">{children}</tbody>
        </table>
      </div>
    </div>
  );
}

// ── Category tab row components ────────────────────────────────────────────────

function LampUpgradeRow({ item }: { item: ClearTypeUpdateItem }) {
  const prevStyle = clearTypeStyle(item.prev_clear_type, true);
  const newStyle = clearTypeStyle(item.new_clear_type, false);

  return (
    <tr className="hover:bg-secondary/30 transition-colors">
      {/* 이전 상태 */}
      <td className="pl-3 pr-1 py-2 w-[96px]">
        <span
          className="inline-flex items-center justify-center rounded px-1.5 py-0.5 text-[10px] font-semibold w-full whitespace-nowrap"
          style={prevStyle}
        >
          {CLEAR_TYPE_LABELS_SIMPLE[item.prev_clear_type ?? 0] ?? "?"}
        </span>
      </td>
      {/* 화살표 */}
      <td className="px-0 w-5">
        <ChevronRight className="w-3 h-3 text-muted-foreground/35 mx-auto" />
      </td>
      {/* 현재 상태 */}
      <td className="pr-3 pl-1 py-2 w-[96px]">
        <span
          className="inline-flex items-center justify-center rounded px-1.5 py-0.5 text-[10px] font-semibold w-full whitespace-nowrap"
          style={newStyle}
        >
          {CLEAR_TYPE_LABELS_SIMPLE[item.new_clear_type ?? 0] ?? "?"}
        </span>
      </td>
      {/* 난이도 */}
      <td className="px-2 py-2 w-[110px]">
        <TableLevelBadges levels={item.table_levels} />
      </td>
      {/* 제목 */}
      <td className="px-2 py-2">
        <p className="text-xs font-medium truncate">{item.title ?? "(알 수 없음)"}</p>
        {item.artist && (
          <p className="text-[10px] text-muted-foreground truncate">{item.artist}</p>
        )}
      </td>
    </tr>
  );
}

// Dim (이전 상태) 버전 — 현재 상태 스타일보다 낮은 opacity
const RANK_DIM_STYLE: Record<string, React.CSSProperties> = {
  MAX: { color: "hsl(330 65% 78% / 0.4)", background: "hsl(330 65% 78% / 0.06)", borderLeft: "2px solid hsl(330 65% 78% / 0.18)" },
  AAA: { color: "hsl(46 80% 60% / 0.4)",  background: "hsl(46 80% 60% / 0.06)",  borderLeft: "2px solid hsl(46 80% 60% / 0.18)" },
  AA:  { color: "hsl(220 15% 72% / 0.4)", background: "hsl(220 15% 72% / 0.06)", borderLeft: "2px solid hsl(220 15% 72% / 0.18)" },
  A:   { color: "hsl(27 65% 55% / 0.4)",  background: "hsl(27 65% 55% / 0.06)",  borderLeft: "2px solid hsl(27 65% 55% / 0.18)" },
  B:   { color: "hsl(var(--clear-normal) / 0.4)", background: "hsl(var(--clear-normal) / 0.05)", borderLeft: "2px solid hsl(var(--clear-normal) / 0.15)" },
  C:   { color: "hsl(var(--clear-easy) / 0.4)",   background: "hsl(var(--clear-easy) / 0.05)",   borderLeft: "2px solid hsl(var(--clear-easy) / 0.15)" },
  D:   { color: "hsl(var(--clear-assist) / 0.4)", background: "hsl(var(--clear-assist) / 0.05)", borderLeft: "2px solid hsl(var(--clear-assist) / 0.15)" },
  E:   { color: "hsl(var(--clear-failed) / 0.4)", background: "hsl(var(--clear-failed) / 0.05)", borderLeft: "2px solid hsl(var(--clear-failed) / 0.15)" },
  F:   { color: "hsl(var(--muted-foreground) / 0.35)", background: "transparent", borderLeft: "2px solid hsl(var(--muted-foreground) / 0.12)" },
};

function ScoreUpgradeRow({ item }: { item: ExscoreUpdateItem }) {
  const prevRankStyle = RANK_DIM_STYLE[item.prev_rank ?? "F"] ?? RANK_DIM_STYLE["F"];
  const newRankStyle = RANK_COLOR_STYLE[item.new_rank ?? "F"] ?? RANK_COLOR_STYLE["F"];
  const scoreDiff =
    item.prev_exscore != null && item.new_exscore != null
      ? item.new_exscore - item.prev_exscore
      : null;

  return (
    <tr className="hover:bg-secondary/30 transition-colors">
      {/* 이전 점수/랭크 */}
      <td className="pl-3 pr-1 py-2 w-[96px]">
        <div className="flex flex-col items-center gap-0.5">
          {item.prev_rank == null ? (
            <span className="text-[9px] text-muted-foreground/40">NO PLAY</span>
          ) : (
            <>
              <span className="text-[10px] font-mono text-muted-foreground/50">
                {item.prev_exscore ?? "–"}
              </span>
              <span
                className="inline-flex items-center justify-center rounded px-2 py-0 text-[10px] font-bold w-full"
                style={prevRankStyle}
              >
                {item.prev_rank}
              </span>
            </>
          )}
        </div>
      </td>
      {/* 화살표 */}
      <td className="px-0 w-5">
        <ChevronRight className="w-3 h-3 text-muted-foreground/35 mx-auto" />
      </td>
      {/* 현재 점수/랭크 */}
      <td className="pr-3 pl-1 py-2 w-[96px]">
        <div className="flex flex-col items-center gap-0.5">
          <div className="flex items-baseline gap-1">
            <span className="text-[10px] font-mono font-semibold text-foreground">
              {item.new_exscore ?? "–"}
            </span>
            {scoreDiff != null && scoreDiff > 0 && (
              <span
                className="text-[11px] font-bold"
                style={{ color: "hsl(var(--clear-fc) / 0.85)" }}
              >
                ▲{scoreDiff}
              </span>
            )}
          </div>
          <span
            className="inline-flex items-center justify-center rounded px-2 py-0 text-[10px] font-bold w-full"
            style={newRankStyle}
          >
            {item.new_rank ?? "–"}
          </span>
        </div>
      </td>
      {/* 난이도 */}
      <td className="px-2 py-2 w-[110px]">
        <TableLevelBadges levels={item.table_levels} />
      </td>
      {/* 제목 */}
      <td className="px-2 py-2">
        <p className="text-xs font-medium truncate">{item.title ?? "(알 수 없음)"}</p>
        {item.artist && (
          <p className="text-[10px] text-muted-foreground truncate">{item.artist}</p>
        )}
      </td>
    </tr>
  );
}

function BPUpgradeRow({ item }: { item: MinBPUpdateItem }) {
  const prev = item.prev_min_bp;
  const next = item.new_min_bp;
  const diff = prev != null && next != null ? prev - next : null;

  return (
    <tr className="hover:bg-secondary/30 transition-colors">
      {/* 이전 BP */}
      <td className="pl-3 pr-1 py-2 w-[60px] text-center">
        {prev == null ? (
          <span className="text-[9px] text-muted-foreground/40">NO PLAY</span>
        ) : (
          <span className="text-[11px] font-mono text-muted-foreground/50">
            {prev}
          </span>
        )}
      </td>
      {/* 화살표 */}
      <td className="px-0 w-5">
        <ChevronRight className="w-3 h-3 text-muted-foreground/35 mx-auto" />
      </td>
      {/* 현재 BP */}
      <td className="pr-3 pl-1 py-2 w-[90px] text-center">
        <div className="flex items-center justify-center gap-1.5">
          <span className="text-[11px] font-mono font-semibold text-foreground">
            {next ?? "–"}
          </span>
          {diff != null && diff > 0 && (
            <span
              className="text-[11px] font-mono font-bold"
              style={{ color: "hsl(var(--clear-hard))" }}
            >
              ▼{diff}
            </span>
          )}
        </div>
      </td>
      {/* 난이도 */}
      <td className="px-2 py-2 w-[110px]">
        <TableLevelBadges levels={item.table_levels} />
      </td>
      {/* 제목 */}
      <td className="px-2 py-2">
        <p className="text-xs font-medium truncate">{item.title ?? "(알 수 없음)"}</p>
        {item.artist && (
          <p className="text-[10px] text-muted-foreground truncate">{item.artist}</p>
        )}
      </td>
    </tr>
  );
}

function ComboUpgradeRow({ item }: { item: MaxComboUpdateItem }) {
  const prev = item.prev_max_combo;
  const next = item.new_max_combo;
  const diff = prev != null && next != null ? next - prev : null;

  return (
    <tr className="hover:bg-secondary/30 transition-colors">
      {/* 이전 Combo */}
      <td className="pl-3 pr-1 py-2 w-[60px] text-center">
        {prev == null ? (
          <span className="text-[9px] text-muted-foreground/40">NO PLAY</span>
        ) : (
          <span className="text-[11px] font-mono text-muted-foreground/50">
            {prev}
          </span>
        )}
      </td>
      {/* 화살표 */}
      <td className="px-0 w-5">
        <ChevronRight className="w-3 h-3 text-muted-foreground/35 mx-auto" />
      </td>
      {/* 현재 Combo */}
      <td className="pr-3 pl-1 py-2 w-[90px] text-center">
        <div className="flex items-center justify-center gap-1.5">
          <span className="text-[11px] font-mono font-semibold text-foreground">
            {next ?? "–"}
          </span>
          {diff != null && diff > 0 && (
            <span
              className="text-[11px] font-mono font-bold"
              style={{ color: "hsl(var(--clear-fc))" }}
            >
              ▲{diff}
            </span>
          )}
        </div>
      </td>
      {/* 난이도 */}
      <td className="px-2 py-2 w-[110px]">
        <TableLevelBadges levels={item.table_levels} />
      </td>
      {/* 제목 */}
      <td className="px-2 py-2">
        <p className="text-xs font-medium truncate">{item.title ?? "(알 수 없음)"}</p>
        {item.artist && (
          <p className="text-[10px] text-muted-foreground truncate">{item.artist}</p>
        )}
      </td>
    </tr>
  );
}

// ── Category tab ───────────────────────────────────────────────────────────────

function CategoryTab({ data }: { data: ScoreUpdatesResponse }) {
  const mergedCourses = useMemo(() => buildMergedCourses(data), [data]);

  const sortedLamp = [...data.clear_type_updates]
    .filter((u) => !u.is_course)
    .sort((a, b) => {
      const ct = (b.new_clear_type ?? 0) - (a.new_clear_type ?? 0);
      if (ct !== 0) return ct;
      const lv = compareByTableLevels(a.table_levels, b.table_levels);
      if (lv !== 0) return lv;
      return compareTitles(a.title ?? "", b.title ?? "");
    });

  const sortedScore = [...data.exscore_updates]
    .filter((u) => !u.is_course)
    .sort((a, b) => {
      const ra = RANK_SORT_ORDER[a.new_rank ?? "F"] ?? 99;
      const rb = RANK_SORT_ORDER[b.new_rank ?? "F"] ?? 99;
      if (ra !== rb) return ra - rb;
      const lv = compareByTableLevels(a.table_levels, b.table_levels);
      if (lv !== 0) return lv;
      return compareTitles(a.title ?? "", b.title ?? "");
    });

  const bpItems = [...data.min_bp_updates].sort((a, b) => {
    const lv = compareByTableLevels(a.table_levels, b.table_levels);
    if (lv !== 0) return lv;
    const da = a.prev_min_bp != null && a.new_min_bp != null ? a.prev_min_bp - a.new_min_bp : -1;
    const db = b.prev_min_bp != null && b.new_min_bp != null ? b.prev_min_bp - b.new_min_bp : -1;
    if (da !== db) return db - da;
    return compareTitles(a.title ?? "", b.title ?? "");
  });

  const comboItems = [...data.max_combo_updates].sort((a, b) => {
    const lv = compareByTableLevels(a.table_levels, b.table_levels);
    if (lv !== 0) return lv;
    const da = a.prev_max_combo != null && a.new_max_combo != null ? a.new_max_combo - a.prev_max_combo : -1;
    const db = b.prev_max_combo != null && b.new_max_combo != null ? b.new_max_combo - b.prev_max_combo : -1;
    if (da !== db) return db - da;
    return compareTitles(a.title ?? "", b.title ?? "");
  });

  const empty =
    mergedCourses.length === 0 &&
    sortedLamp.length === 0 &&
    sortedScore.length === 0 &&
    bpItems.length === 0 &&
    comboItems.length === 0;

  if (empty) {
    return (
      <p className="text-sm text-muted-foreground text-center py-8">
        기록 갱신 데이터가 없습니다.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {/* Course records */}
      {mergedCourses.length > 0 && (
        <div className="border border-border/40 rounded-lg p-3">
          <p className="text-xs font-semibold text-muted-foreground mb-2">
            Course Records ({mergedCourses.length})
          </p>
          {mergedCourses.map((c, i) => (
            <CourseUpdateRow key={i} item={c} />
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* Lamp Upgrade */}
        {sortedLamp.length > 0 && (
          <SectionTable title="Lamp Upgrade" count={sortedLamp.length}>
            {sortedLamp.map((item, i) => (
              <LampUpgradeRow key={i} item={item} />
            ))}
          </SectionTable>
        )}

        {/* Score Upgrade */}
        {sortedScore.length > 0 && (
          <SectionTable title="Score Upgrade" count={sortedScore.length}>
            {sortedScore.map((item, i) => (
              <ScoreUpgradeRow key={i} item={item} />
            ))}
          </SectionTable>
        )}

        {/* BP Upgrade */}
        {bpItems.length > 0 && (
          <SectionTable title="BP Upgrade" count={bpItems.length}>
            {bpItems.map((item, i) => (
              <BPUpgradeRow key={i} item={item} />
            ))}
          </SectionTable>
        )}

        {/* Max Combo Upgrade */}
        {comboItems.length > 0 && (
          <SectionTable title="Max Combo Upgrade" count={comboItems.length}>
            {comboItems.map((item, i) => (
              <ComboUpgradeRow key={i} item={item} />
            ))}
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
  client_types: Set<string>;
  clear?: { prev: number | null; new: number | null };
  score?: { prev: number | null; new: number | null; prev_rank: string | null; new_rank: string | null };
  bp?: { prev: number | null; new: number | null };
  combo?: { prev: number | null; new: number | null };
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
  ): MergedFumenUpdate {
    const key = sha256 ?? md5 ?? `unknown-${Math.random()}`;
    if (!map.has(key)) {
      map.set(key, { sha256, md5, title, artist, table_levels, client_type, client_types: new Set([client_type]) });
    } else {
      map.get(key)!.client_types.add(client_type);
    }
    return map.get(key)!;
  }

  for (const item of data.clear_type_updates) {
    if (item.is_course) continue;
    const entry = getOrCreate(item.fumen_sha256, item.fumen_md5, item.title, item.artist, item.table_levels, item.client_type);
    entry.clear = { prev: item.prev_clear_type, new: item.new_clear_type };
  }

  for (const item of data.exscore_updates) {
    if (item.is_course) continue;
    const entry = getOrCreate(item.fumen_sha256, item.fumen_md5, item.title, item.artist, item.table_levels, item.client_type);
    entry.score = { prev: item.prev_exscore, new: item.new_exscore, prev_rank: item.prev_rank, new_rank: item.new_rank };
  }

  for (const item of data.min_bp_updates) {
    const entry = getOrCreate(item.fumen_sha256, item.fumen_md5, item.title, item.artist, item.table_levels, item.client_type);
    entry.bp = { prev: item.prev_min_bp, new: item.new_min_bp };
  }

  for (const item of data.max_combo_updates) {
    const entry = getOrCreate(item.fumen_sha256, item.fumen_md5, item.title, item.artist, item.table_levels, item.client_type);
    entry.combo = { prev: item.prev_max_combo, new: item.new_max_combo };
  }

  return Array.from(map.values())
    .filter((f) => f.clear || f.score || f.bp || f.combo)
    .sort((a, b) => {
      const aClear = a.clear?.new ?? -1;
      const bClear = b.clear?.new ?? -1;
      if (aClear !== bClear) return bClear - aClear;

      const aRank = a.score?.new_rank ? (RANK_SORT_ORDER[a.score.new_rank] ?? 99) : 99;
      const bRank = b.score?.new_rank ? (RANK_SORT_ORDER[b.score.new_rank] ?? 99) : 99;
      if (aRank !== bRank) return aRank - bRank;

      return (a.title ?? "").localeCompare(b.title ?? "");
    });
}

function FumenRow({ fumen }: { fumen: MergedFumenUpdate }) {
  const rowBg = fumen.clear?.new != null ? (CLEAR_ROW_BG[fumen.clear.new] ?? "") : "";

  return (
    <tr className={cn("transition-colors hover:bg-secondary/50", rowBg)}>
      {/* Level: table membership badges */}
      <td className="px-3 py-2 align-top">
        <TableLevelBadges levels={fumen.table_levels} />
      </td>

      {/* Title + Artist */}
      <td className="px-3 py-2 align-top max-w-[220px]">
        <p className="text-xs font-medium truncate">{fumen.title ?? "(알 수 없음)"}</p>
        {fumen.artist && (
          <p className="text-[10px] text-muted-foreground truncate">{fumen.artist}</p>
        )}
      </td>

      {/* Lamp: prev → new */}
      <td className="px-3 py-2 align-top">
        {fumen.clear ? (
          <div className="flex items-center gap-1 whitespace-nowrap">
            <span className="text-[10px] text-muted-foreground">
              {CLEAR_TYPE_LABELS_SIMPLE[fumen.clear.prev ?? 0] ?? "?"}
            </span>
            <span className="text-[10px] text-muted-foreground">→</span>
            {clearBadge(fumen.clear.new, fumen.client_type)}
          </div>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </td>

      {/* Score: prev → new */}
      <td className="px-3 py-2 text-right font-mono align-top whitespace-nowrap">
        {fumen.score ? (
          <span className="text-xs text-muted-foreground">
            {fumen.score.prev ?? "?"}{" "}
            <span className="text-foreground font-bold">→ {fumen.score.new ?? "?"}</span>
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </td>

      {/* Rank: prev → new */}
      <td className="px-3 py-2 text-center font-mono align-top whitespace-nowrap">
        {fumen.score?.new_rank ? (
          <span className="text-xs text-muted-foreground">
            {fumen.score.prev_rank ?? "?"}
            {" → "}
            <span className="text-foreground">{fumen.score.new_rank}</span>
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </td>

      {/* BP: prev → new */}
      <td className="px-3 py-2 text-right font-mono align-top whitespace-nowrap">
        {fumen.bp ? (
          <span className="text-xs text-muted-foreground">
            {fumen.bp.prev ?? "?"}{" "}
            <span className="text-foreground">→ {fumen.bp.new ?? "?"}</span>
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </td>

      {/* Combo: prev → new */}
      <td className="px-3 py-2 text-right font-mono align-top whitespace-nowrap">
        {fumen.combo ? (
          <span className="text-xs text-muted-foreground">
            {fumen.combo.prev ?? "?"}{" "}
            <span className="text-foreground">→ {fumen.combo.new ?? "?"}</span>
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </td>

      {/* Client */}
      <td className="px-3 py-2 text-center align-top">
        <span className="text-[10px] font-mono px-1 py-0.5 rounded border border-border/60 text-muted-foreground">
          {fumen.client_types.size > 1
            ? "MIX"
            : fumen.client_type === "lr2"
            ? "LR"
            : fumen.client_type === "beatoraja"
            ? "BR"
            : fumen.client_type}
        </span>
      </td>
    </tr>
  );
}

function FumenTab({ data }: { data: ScoreUpdatesResponse }) {
  const fumens = useMemo(() => buildMergedFumens(data), [data]);
  const mergedCourses = useMemo(() => buildMergedCourses(data), [data]);

  const empty = mergedCourses.length === 0 && fumens.length === 0;

  if (empty) {
    return (
      <p className="text-sm text-muted-foreground text-center py-8">
        기록 갱신 데이터가 없습니다.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {/* Course records */}
      {mergedCourses.length > 0 && (
        <div className="border border-border/40 rounded-lg p-3">
          <p className="text-xs font-semibold text-muted-foreground mb-2">
            Course Records ({mergedCourses.length})
          </p>
          {mergedCourses.map((c, i) => (
            <CourseUpdateRow key={i} item={c} />
          ))}
        </div>
      )}

      {/* Fumen table */}
      {fumens.length > 0 && (
        <div className="border border-border/40 rounded-lg overflow-hidden">
          <div className="overflow-auto max-h-[480px]">
            <table className="w-full text-xs min-w-[640px]">
              <thead className="sticky top-0 z-10 bg-card border-b border-border/50">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground select-none whitespace-nowrap">
                    Level
                  </th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground select-none">
                    Title
                  </th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground select-none whitespace-nowrap">
                    Lamp
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-muted-foreground select-none">
                    Score
                  </th>
                  <th className="px-3 py-2 text-center font-medium text-muted-foreground select-none">
                    Rank
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-muted-foreground select-none">
                    BP
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-muted-foreground select-none">
                    Combo
                  </th>
                  <th className="px-3 py-2 text-center font-medium text-muted-foreground select-none">
                    Client
                  </th>
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
}

const TAB_DESCRIPTIONS: Record<string, string> = {
  category: "카테고리 기준으로 표시",
  fumen: "차분 기준으로 표시",
};

export function ScoreUpdates({ clientType, date, limit = 50 }: ScoreUpdatesProps) {
  const { data, isLoading } = useScoreUpdates(clientType, date, limit);
  const [activeTab, setActiveTab] = useState<"category" | "fumen">("category");

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">기록 갱신</CardTitle>
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
            value={activeTab}
            onValueChange={(v) => setActiveTab(v as "category" | "fumen")}
          >
            <div className="flex items-center gap-3 mb-4">
              <TabsList>
                <TabsTrigger value="category">카테고리</TabsTrigger>
                <TabsTrigger value="fumen">차분</TabsTrigger>
              </TabsList>
              <p className="text-[10px] text-muted-foreground">
                {TAB_DESCRIPTIONS[activeTab]}
              </p>
            </div>
            <TabsContent value="category">
              <CategoryTab data={data} />
            </TabsContent>
            <TabsContent value="fumen">
              <FumenTab data={data} />
            </TabsContent>
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}
