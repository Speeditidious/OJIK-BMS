"use client";

import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { ScoreUpdatesResponse, ClearTypeUpdateItem, ExscoreUpdateItem } from "@/types";
import type { DayStatSheetPrefs, UpdateSectionKey } from "@/hooks/use-preferences";
import {
  SectionTable, LampUpgradeRow, ScoreUpgradeRow, BPUpgradeRow, ComboUpgradeRow,
  CourseSectionTable, CourseTableRow,
  buildMergedCourses,
} from "@/components/dashboard/ScoreUpdates";
import { compareByTableLevels } from "@/components/common/TableLevelBadges";
import { RANK_SORT_ORDER } from "@/lib/score-rank-display-core.mjs";
import { useScoreUpdatesPrefs, useUpdateScoreUpdatesPrefs } from "@/hooks/use-preferences";
import { useAuthStore } from "@/stores/auth";

// --- Type-grouped sub-header ---

const CLEAR_TYPE_LABELS_SIMPLE: Record<number, string> = {
  0: "NO PLAY", 1: "FAILED", 2: "ASSIST", 3: "EASY", 4: "NORMAL",
  5: "HARD", 6: "EX HARD", 7: "FULL COMBO", 8: "PERFECT", 9: "MAX",
};

const CLEAR_TYPE_COLOR: Record<number, string> = {
  0: "hsl(var(--clear-no-play))", 1: "hsl(var(--clear-failed))", 2: "hsl(var(--clear-assist))",
  3: "hsl(var(--clear-easy))", 4: "hsl(var(--clear-normal))", 5: "hsl(var(--clear-hard))",
  6: "hsl(var(--clear-exhard))", 7: "hsl(var(--clear-fc))", 8: "hsl(var(--clear-perfect))", 9: "hsl(var(--clear-max))",
};

const RANK_COLOR: Record<string, string> = {
  F: "hsl(var(--clear-no-play))", E: "hsl(var(--clear-failed))", D: "hsl(var(--clear-assist))",
  C: "hsl(var(--clear-easy))", B: "hsl(var(--clear-normal))", A: "hsl(27 65% 55%)",
  AA: "hsl(220 15% 72%)", AAA: "hsl(46 80% 60%)", "MAX-": "hsl(330 65% 78%)",
};

function ClearTypeGroupHeader({ label, count, ct }: { label: string; count: number; ct: number }) {
  const color = CLEAR_TYPE_COLOR[ct] ?? "hsl(var(--clear-no-play))";
  return (
    <tr data-day-sheet-split-block data-day-sheet-keep-with-next>
      <td colSpan={4} className="px-4 py-2 text-center bg-muted/20 border-y-2" style={{ borderColor: color }}>
        <span className="text-base font-bold" style={{ color }}>{label}</span>
        <span className="text-base font-normal text-muted-foreground ml-2">{count}건</span>
      </td>
    </tr>
  );
}

function RankGroupHeader({ label, count, rank }: { label: string; count: number; rank: string }) {
  const color = RANK_COLOR[rank] ?? "hsl(var(--clear-no-play))";
  return (
    <tr data-day-sheet-split-block data-day-sheet-keep-with-next>
      <td colSpan={4} className="px-4 py-2 text-center bg-muted/20 border-y-2" style={{ borderColor: color }}>
        <span className="text-base font-bold" style={{ color }}>{label}</span>
        <span className="text-base font-normal text-muted-foreground ml-2">{count}건</span>
      </td>
    </tr>
  );
}

// --- Section label helper ---

function useSectionLabel(): (key: UpdateSectionKey) => string {
  const { t } = useTranslation();
  return (key) => {
    switch (key) {
      case "clear": return t("dashboard.daySheet.sectionClear");
      case "score": return t("dashboard.daySheet.sectionScore");
      case "bp": return t("dashboard.daySheet.sectionBp");
      case "combo": return t("dashboard.daySheet.sectionCombo");
    }
  };
}

// --- UpdateSections props ---

interface UpdateSectionsProps {
  data: ScoreUpdatesResponse;
  userId?: string;
  asOf?: string;
  prefs: DayStatSheetPrefs;
  onPrefsChange?: (p: Partial<DayStatSheetPrefs>) => void;
  /** "tab": interactive (scrollable, new-play toggle); "sheet": export-friendly (no scroll cap) */
  variant?: "tab" | "sheet";
}

export function UpdateSections({
  data,
  userId,
  asOf,
  prefs,
  onPrefsChange,
  variant = "tab",
}: UpdateSectionsProps) {
  const { t } = useTranslation();
  const newPlayPrefs = useScoreUpdatesPrefs();
  const { mutate: updateNewPlayPrefs } = useUpdateScoreUpdatesPrefs();
  const { user, isInitialized } = useAuthStore();
  const canPersist = isInitialized && !!user;
  const sectionLabel = useSectionLabel();

  const mergedCourses = useMemo(() => buildMergedCourses(data), [data]);

  // --- Base sorted arrays ---
  const lampAll = useMemo(
    () =>
      [...data.clear_type_updates]
        .filter((u) => !u.is_course)
        .sort((a, b) => {
          const ct = (b.new_clear_type ?? 0) - (a.new_clear_type ?? 0);
          return ct !== 0 ? ct : compareByTableLevels(a.table_levels, b.table_levels);
        }),
    [data],
  );

  const scoreAll = useMemo(
    () =>
      [...data.exscore_updates]
        .filter((u) => !u.is_course)
        .sort((a, b) => {
          const ra = RANK_SORT_ORDER[a.new_rank ?? "F"] ?? 99;
          const rb = RANK_SORT_ORDER[b.new_rank ?? "F"] ?? 99;
          const rank = ra - rb;
          return rank !== 0 ? rank : compareByTableLevels(a.table_levels, b.table_levels);
        }),
    [data],
  );

  const bpAll = useMemo(
    () =>
      [...data.min_bp_updates].sort((a, b) => {
        const aDiff = a.prev_min_bp != null && a.new_min_bp != null ? a.prev_min_bp - a.new_min_bp : -1;
        const bDiff = b.prev_min_bp != null && b.new_min_bp != null ? b.prev_min_bp - b.new_min_bp : -1;
        return bDiff - aDiff !== 0 ? bDiff - aDiff : compareByTableLevels(a.table_levels, b.table_levels);
      }),
    [data],
  );

  const comboAll = useMemo(
    () =>
      [...data.max_combo_updates].sort((a, b) => {
        const aDiff = a.prev_max_combo != null && a.new_max_combo != null ? a.new_max_combo - a.prev_max_combo : -1;
        const bDiff = b.prev_max_combo != null && b.new_max_combo != null ? b.new_max_combo - b.prev_max_combo : -1;
        return bDiff - aDiff !== 0 ? bDiff - aDiff : compareByTableLevels(a.table_levels, b.table_levels);
      }),
    [data],
  );

  // --- New-play filtering ---
  const lamp = useMemo(
    () => (newPlayPrefs.score_updates_lamp_include_new_plays ? lampAll : lampAll.filter((u) => !u.is_new_play)),
    [lampAll, newPlayPrefs.score_updates_lamp_include_new_plays],
  );
  const score = useMemo(
    () => (newPlayPrefs.score_updates_score_include_new_plays ? scoreAll : scoreAll.filter((u) => !u.is_new_play)),
    [scoreAll, newPlayPrefs.score_updates_score_include_new_plays],
  );
  const bp = useMemo(
    () => (newPlayPrefs.score_updates_bp_include_new_plays ? bpAll : bpAll.filter((u) => !u.is_new_play)),
    [bpAll, newPlayPrefs.score_updates_bp_include_new_plays],
  );
  const combo = useMemo(
    () => (newPlayPrefs.score_updates_combo_include_new_plays ? comboAll : comboAll.filter((u) => !u.is_new_play)),
    [comboAll, newPlayPrefs.score_updates_combo_include_new_plays],
  );

  // --- Type-grouped rows for clear/score ---
  const lampByType = useMemo(() => {
    const groups: Record<number, ClearTypeUpdateItem[]> = {};
    for (const item of lamp) {
      const ct = item.new_clear_type ?? 0;
      if (!groups[ct]) groups[ct] = [];
      groups[ct].push(item);
    }
    return Object.entries(groups)
      .sort(([a], [b]) => Number(b) - Number(a))
      .map(([ct, items]) => ({ ct: Number(ct), items }));
  }, [lamp]);

  const scoreByRank = useMemo(() => {
    const groups: Record<string, ExscoreUpdateItem[]> = {};
    for (const item of score) {
      const r = item.new_rank ?? "F";
      if (!groups[r]) groups[r] = [];
      groups[r].push(item);
    }
    return Object.entries(groups)
      .sort(([a], [b]) => (RANK_SORT_ORDER[a] ?? 99) - (RANK_SORT_ORDER[b] ?? 99))
      .map(([rank, items]) => ({ rank, items }));
  }, [score]);

  // Clear-type / rank detail filters apply to the day-stat sheet only.
  const applyDetailFilter = variant === "sheet";
  const hiddenClearTypes = useMemo(
    () => new Set(applyDetailFilter ? prefs.day_sheet_clear_type_hidden ?? [] : []),
    [applyDetailFilter, prefs.day_sheet_clear_type_hidden],
  );
  const hiddenRanks = useMemo(
    () => new Set(applyDetailFilter ? prefs.day_sheet_score_rank_hidden ?? [] : []),
    [applyDetailFilter, prefs.day_sheet_score_rank_hidden],
  );

  const lampByTypeVisible = useMemo(
    () => lampByType.filter((g) => !hiddenClearTypes.has(g.ct)),
    [lampByType, hiddenClearTypes],
  );
  const scoreByRankVisible = useMemo(
    () => scoreByRank.filter((g) => !hiddenRanks.has(g.rank)),
    [scoreByRank, hiddenRanks],
  );
  const lampVisibleCount = useMemo(
    () => lampByTypeVisible.reduce((sum, g) => sum + g.items.length, 0),
    [lampByTypeVisible],
  );
  const scoreVisibleCount = useMemo(
    () => scoreByRankVisible.reduce((sum, g) => sum + g.items.length, 0),
    [scoreByRankVisible],
  );

  // --- Visibility & ordering ---
  const order = prefs.day_sheet_update_order ?? ["clear", "score", "bp", "combo"];
  const visible = prefs.day_sheet_update_visible ?? { clear: true, score: true, bp: false, combo: false };
  const fullwidth = new Set(prefs.day_sheet_update_fullwidth ?? []);

  const summaryCourses = useMemo(
    () => mergedCourses.filter((c) => c.clear || c.score || c.bp),
    [mergedCourses],
  );

  const visibleSections = order.filter((key) => {
    if (key === "clear") return lampByTypeVisible.length > 0 && (visible.clear !== false);
    if (key === "score") return scoreByRankVisible.length > 0 && (visible.score !== false);
    if (key === "bp") return bpAll.length > 0 && visible.bp;
    if (key === "combo") return comboAll.length > 0 && visible.combo;
    return false;
  });

  const empty =
    summaryCourses.length === 0 &&
    lampAll.length === 0 &&
    scoreAll.length === 0 &&
    bpAll.length === 0 &&
    comboAll.length === 0;

  if (empty) {
    return (
      <p className="text-body text-muted-foreground text-center py-8">
        {t("dashboard.scoreUpdates.noUpdates")}
      </p>
    );
  }

  // Render a section by key
  function renderSection(key: UpdateSectionKey): React.ReactNode {
    const isFullWidth = fullwidth.has(key);
    if (key === "clear" && lampByTypeVisible.length > 0) {
      return (
        <SectionTable
          key="clear"
          title={t("dashboard.scoreUpdates.updateSection", { label: sectionLabel("clear") })}
          count={lampVisibleCount}
          showNewPlays={newPlayPrefs.score_updates_lamp_include_new_plays}
          onToggleNewPlays={
            canPersist && onPrefsChange
              ? () => updateNewPlayPrefs({ score_updates_lamp_include_new_plays: !newPlayPrefs.score_updates_lamp_include_new_plays })
              : undefined
          }
          fullWidth={isFullWidth}
          onToggleFullWidth={
            canPersist && onPrefsChange
              ? () => {
                  const next = isFullWidth
                    ? (prefs.day_sheet_update_fullwidth ?? []).filter((k) => k !== "clear")
                    : [...(prefs.day_sheet_update_fullwidth ?? []), "clear" as UpdateSectionKey];
                  onPrefsChange({ day_sheet_update_fullwidth: next });
                }
              : undefined
          }
        >
          {lampByTypeVisible.map(({ ct, items }) => (
            <React.Fragment key={ct}>
              <ClearTypeGroupHeader label={CLEAR_TYPE_LABELS_SIMPLE[ct] ?? String(ct)} count={items.length} ct={ct} />
              {items.map((item, i) => <LampUpgradeRow key={i} item={item} userId={userId} asOf={asOf} />)}
            </React.Fragment>
          ))}
        </SectionTable>
      );
    }

    if (key === "score" && scoreByRankVisible.length > 0 && visible.score !== false) {
      return (
        <SectionTable
          key="score"
          title={t("dashboard.scoreUpdates.updateSection", { label: sectionLabel("score") })}
          count={scoreVisibleCount}
          showNewPlays={newPlayPrefs.score_updates_score_include_new_plays}
          onToggleNewPlays={
            canPersist && onPrefsChange
              ? () => updateNewPlayPrefs({ score_updates_score_include_new_plays: !newPlayPrefs.score_updates_score_include_new_plays })
              : undefined
          }
          fullWidth={isFullWidth}
          onToggleFullWidth={
            canPersist && onPrefsChange
              ? () => {
                  const next = isFullWidth
                    ? (prefs.day_sheet_update_fullwidth ?? []).filter((k) => k !== "score")
                    : [...(prefs.day_sheet_update_fullwidth ?? []), "score" as UpdateSectionKey];
                  onPrefsChange({ day_sheet_update_fullwidth: next });
                }
              : undefined
          }
        >
          {scoreByRankVisible.map(({ rank, items }) => (
            <React.Fragment key={rank}>
              <RankGroupHeader label={rank} count={items.length} rank={rank} />
              {items.map((item, i) => <ScoreUpgradeRow key={i} item={item} userId={userId} asOf={asOf} />)}
            </React.Fragment>
          ))}
        </SectionTable>
      );
    }

    if (key === "bp" && bpAll.length > 0 && visible.bp) {
      return (
        <SectionTable
          key="bp"
          title={t("dashboard.scoreUpdates.updateSection", { label: sectionLabel("bp") })}
          count={bp.length}
          showNewPlays={newPlayPrefs.score_updates_bp_include_new_plays}
          onToggleNewPlays={
            canPersist && onPrefsChange
              ? () => updateNewPlayPrefs({ score_updates_bp_include_new_plays: !newPlayPrefs.score_updates_bp_include_new_plays })
              : undefined
          }
          fullWidth={isFullWidth}
        >
          {bp.map((item, i) => <BPUpgradeRow key={i} item={item} userId={userId} asOf={asOf} />)}
        </SectionTable>
      );
    }

    if (key === "combo" && comboAll.length > 0 && visible.combo) {
      return (
        <SectionTable
          key="combo"
          title={t("dashboard.scoreUpdates.maxComboUpdates")}
          count={combo.length}
          showNewPlays={newPlayPrefs.score_updates_combo_include_new_plays}
          onToggleNewPlays={
            canPersist && onPrefsChange
              ? () => updateNewPlayPrefs({ score_updates_combo_include_new_plays: !newPlayPrefs.score_updates_combo_include_new_plays })
              : undefined
          }
          fullWidth={isFullWidth}
        >
          {combo.map((item, i) => <ComboUpgradeRow key={i} item={item} userId={userId} asOf={asOf} />)}
        </SectionTable>
      );
    }

    return null;
  }

  // Partition sections into normal (2-col) and fullwidth (single row)
  // Render in order, grouping consecutive non-fullwidth into grids
  const rendered: React.ReactNode[] = [];
  let normalBatch: React.ReactNode[] = [];

  function flushNormal() {
    if (normalBatch.length === 0) return;
    rendered.push(
      <div key={`batch-${rendered.length}`} className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {normalBatch}
      </div>,
    );
    normalBatch = [];
  }

  for (const key of visibleSections) {
    const node = renderSection(key);
    if (!node) continue;
    if (fullwidth.has(key)) {
      flushNormal();
      rendered.push(<div key={key}>{node}</div>);
    } else {
      normalBatch.push(<div key={key}>{node}</div>);
    }
  }
  flushNormal();

  return (
    <div className="space-y-3">
      {summaryCourses.length > 0 && (
        <div>
          <CourseSectionTable
            title={t("dashboard.scoreUpdates.courseRecords")}
            count={summaryCourses.length}
          >
            {summaryCourses.map((c, i) => (
              <CourseTableRow key={i} item={c} userId={userId} asOf={asOf} />
            ))}
          </CourseSectionTable>
        </div>
      )}
      {rendered}
    </div>
  );
}
