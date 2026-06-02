"use client";

import Link from "next/link";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import { useScoreRowDetail } from "@/hooks/use-score-row-detail";
import { useCourseRowDetail } from "@/hooks/use-course-row-detail";
import { UnavailableValue } from "@/components/common/UnavailableValue";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ARRANGEMENT_KANJI } from "@/lib/fumen-table-utils";
import {
  JUDGMENT_STYLE,
  ARRANGEMENT_REASON_I18N_KEY,
  laneIsWhiteKey,
} from "@/lib/score-row-detail-core.mjs";

import type { CourseRowDetailRecord, RowDetailRecord, LaneGroup } from "@/lib/score-row-detail-types";
import type { UserScore } from "@/types";

// ── Section heading ──────────────────────────────────────────────────────────

function SectionLabel({ label }: { label: string }) {
  return (
    <p className="text-caption text-muted-foreground/70 text-center uppercase tracking-widest mb-1.5">
      {label}
    </p>
  );
}

// ── Judgment section ─────────────────────────────────────────────────────────

function JudgmentSection({ record }: { record: RowDetailRecord }) {
  const { t } = useTranslation();
  const detail = record.judgment_detail;
  if (!detail) return null;
  const isLr2 = record.client_type === "lr2";
  const isBeatoraja = record.client_type === "beatoraja";

  const fast = detail.fast_total_excluding_pgreat;
  const slow = detail.slow_total_excluding_pgreat;
  const showTotals = isBeatoraja && (fast !== null || slow !== null);

  // LR2 does not have a Miss judgment
  const visibleJudgments = isLr2
    ? detail.judgments.filter((jg) => jg.key !== "miss")
    : detail.judgments;

  return (
    <div className="flex flex-col items-center gap-1.5">
      <SectionLabel label={t("fumenRowDetail.judgments")} />
      <div>
        <table className="text-label border-collapse">
          <tbody>
            {visibleJudgments.map((jg) => {
              const style = JUDGMENT_STYLE[jg.key] ?? { color: "text-foreground" };
              const label =
                jg.key === "pgreat"
                  ? "PGreat"
                  : jg.key.charAt(0).toUpperCase() + jg.key.slice(1);
              return (
                <tr key={jg.key} className="leading-snug">
                  <td className={cn("pr-2.5 font-semibold whitespace-nowrap", style.color)}>
                    {label}
                  </td>
                  <td className="pr-3 tabular-nums text-right text-foreground font-medium">
                    {jg.count.toLocaleString()}
                  </td>
                  {isBeatoraja && (
                    <>
                      <td className="pr-1.5 tabular-nums text-right text-blue-400/80 text-caption">
                        {jg.fast !== null ? `F ${jg.fast}` : ""}
                      </td>
                      <td className="tabular-nums text-right text-rose-400/80 text-caption">
                        {jg.slow !== null ? `S ${jg.slow}` : ""}
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
        {showTotals && (
          <p className="mt-1 text-caption text-muted-foreground/60">
            {t("fumenRowDetail.fastSlowTotalExPgreat", {
              fast: fast ?? 0,
              slow: slow ?? 0,
            })}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Lane group display ────────────────────────────────────────────────────────

function LaneGroupDisplay({
  group,
  keymode,
  label,
}: {
  group: LaneGroup;
  keymode: number | null;
  label?: string;
}) {
  return (
    <div className="flex flex-col items-center gap-1">
      {label && (
        <span className="text-caption font-semibold text-muted-foreground/70 uppercase tracking-wider">
          {label}
        </span>
      )}
      <div className="flex gap-px">
        {group.lanes.map((lane, idx) => {
          const isWhite = laneIsWhiteKey(keymode ?? group.lanes.length, lane);
          return (
            <div
              key={idx}
              className={cn(
                "flex items-center justify-center text-caption select-none",
                "w-6 h-9 rounded-sm",
                isWhite
                  ? "bg-slate-200 dark:bg-slate-200/20 text-slate-700 dark:text-slate-200/90 border border-slate-300 dark:border-slate-200/30"
                  : "bg-slate-700 dark:bg-zinc-900 text-slate-200 dark:text-zinc-500 border border-slate-600 dark:border-zinc-700/60",
              )}
            >
              {lane}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function UnknownLaneGroupDisplay({
  keymode,
  reason,
}: {
  keymode: number | null;
  reason: string | null;
}) {
  const { t } = useTranslation();
  const count = keymode ?? 7;
  const i18nKey =
    reason
      ? (ARRANGEMENT_REASON_I18N_KEY[reason] ?? `fumenRowDetail.unavailableReason.${reason}`)
      : null;

  const keys = (
    <div className="flex gap-px cursor-default">
      {Array.from({ length: count }, (_, i) => i + 1).map((lane) => (
        <div
          key={lane}
          className="flex items-center justify-center text-caption select-none w-6 h-9 rounded-sm bg-violet-500/10 text-violet-400/70 border border-violet-500/25"
        >
          ?
        </div>
      ))}
    </div>
  );

  if (!i18nKey) return keys;

  return (
    <TooltipProvider delayDuration={100}>
      <Tooltip>
        <TooltipTrigger asChild>{keys}</TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs text-label">
          {t(i18nKey)}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// ── Arrangement section ───────────────────────────────────────────────────────

function ArrangementSection({
  record,
  keymode,
}: {
  record: RowDetailRecord;
  keymode: number | null;
}) {
  const { t } = useTranslation();
  const arr = record.arrangement;
  if (!arr) return null;

  const rawLabel = arr.option_label ?? "NORMAL";
  const displayLabel = ARRANGEMENT_KANJI[rawLabel] ?? rawLabel;
  const isUnavailable = arr.unavailable_reason !== null || arr.lane_groups === null;

  return (
    <div className="flex flex-col items-center gap-1.5">
      <SectionLabel label={t("fumenRowDetail.arrangement")} />
      <div className="flex items-center gap-1.5 text-label text-foreground/80">
        <span>{displayLabel}</span>
        {arr.double_option_label && (
          <span className="text-muted-foreground/60">
            + {ARRANGEMENT_KANJI[arr.double_option_label] ?? arr.double_option_label}
          </span>
        )}
      </div>
      {isUnavailable ? (
        <UnknownLaneGroupDisplay keymode={keymode} reason={arr.unavailable_reason} />
      ) : (
        <div className="flex gap-3">
          {arr.lane_groups!.map((group, idx) => {
            const isDP = arr.lane_groups!.length > 1;
            const sideLabel = isDP
              ? group.side === "1p" ? "1P" : group.side === "2p" ? "2P" : group.side.toUpperCase()
              : undefined;
            return (
              <LaneGroupDisplay
                key={idx}
                group={group}
                keymode={keymode}
                label={sideLabel}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Client label ──────────────────────────────────────────────────────────────

function ClientSection({ record }: { record: RowDetailRecord }) {
  const { t } = useTranslation();
  const label =
    record.client_type === "lr2"
      ? t("fumenRowDetail.clientLabel.lr2")
      : record.client_type === "beatoraja"
      ? t("fumenRowDetail.clientLabel.beatoraja")
      : record.client_type.toUpperCase();

  return (
    <div className="flex flex-col items-center gap-1.5">
      <SectionLabel label={t("fumenRowDetail.client")} />
      <span className="text-label font-semibold text-foreground">{label}</span>
    </div>
  );
}

// ── Record card ───────────────────────────────────────────────────────────────

function RecordCard({
  record,
  keymode,
}: {
  record: RowDetailRecord;
  keymode: number | null;
}) {
  const hasJudgments = record.judgment_detail !== null;
  const hasArrangement = record.arrangement !== null;
  if (!hasJudgments && !hasArrangement) return null;

  return (
    <div className="flex flex-wrap justify-center gap-x-8 gap-y-3 py-3 px-4">
      <ClientSection record={record} />
      {hasJudgments && <JudgmentSection record={record} />}
      {hasArrangement && <ArrangementSection record={record} keymode={keymode} />}
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

interface FumenRowDetailProps {
  fumenId: string | null | undefined;
  scoreId?: string | null;
  userId?: string | null;
  asOf?: string | null;
}

/**
 * Expanded-row detail panel for a fumen in a table or song list.
 * Lazy-fetches judgment and arrangement details on mount.
 */
export function FumenRowDetail({ fumenId, scoreId, userId, asOf }: FumenRowDetailProps) {
  const { t } = useTranslation();
  const { data, isLoading, isError } = useScoreRowDetail({
    fumenId,
    scoreId,
    userId,
    asOf,
    enabled: !!scoreId || !!fumenId,
  });

  if (!scoreId && !fumenId) return null;

  if (isLoading) {
    return (
      <div className="px-3 py-2 text-label text-muted-foreground">
        {t("fumenRowDetail.loading")}
      </div>
    );
  }

  if (isError || !data) return null;

  if (data.records.length === 0) {
    return (
      <div className="px-3 py-2 text-label text-muted-foreground">
        {t("fumenRowDetail.noRecords")}
      </div>
    );
  }

  const hasContent = data.records.some(
    (r) => r.judgment_detail !== null || r.arrangement !== null
  );
  if (!hasContent) return null;

  return (
    <div className="border-t border-border/30 bg-muted/10 flex flex-wrap justify-center divide-x divide-border/30">
      {data.records.map((record) => (
        <RecordCard key={record.score_id} record={record} keymode={data.keymode} />
      ))}
    </div>
  );
}

// ── Course record card ────────────────────────────────────────────────────────

function CourseRecordCard({ record }: { record: CourseRowDetailRecord }) {
  const { t } = useTranslation();
  const judgmentRecord: RowDetailRecord = {
    score_id: record.score_id,
    client_type: record.client_type,
    clear_type: null,
    min_bp: null,
    rate: null,
    rank: null,
    exscore: null,
    play_count: null,
    judgment_detail: record.judgment_detail,
    arrangement: null,
  };

  const displayLabel = record.option_label
    ? (ARRANGEMENT_KANJI[record.option_label] ?? record.option_label)
    : null;

  return (
    <div className="flex flex-wrap justify-center gap-x-8 gap-y-3 py-3 px-4">
      <ClientSection record={judgmentRecord} />
      {record.judgment_detail && <JudgmentSection record={judgmentRecord} />}
      <div className="flex flex-col items-center gap-1.5">
        <SectionLabel label={t("fumenRowDetail.arrangement")} />
        {displayLabel ? (
          <span className="text-label text-foreground/80">{displayLabel}</span>
        ) : (
          <UnavailableValue reason="score_metadata_missing" />
        )}
      </div>
    </div>
  );
}

interface CourseRowDetailProps {
  courseHash: string | null | undefined;
  clientType: string | null | undefined;
  scoreId?: string | null;
  userId?: string | null;
  asOf?: string | null;
}

/** Expanded aggregate detail panel for a course score row. */
export function CourseRowDetail({ courseHash, clientType, scoreId, userId, asOf }: CourseRowDetailProps) {
  const { t } = useTranslation();
  const { data, isLoading, isError } = useCourseRowDetail({
    courseHash,
    clientType,
    scoreId,
    userId,
    asOf,
    enabled: !!courseHash && !!clientType,
  });

  if (!courseHash || !clientType) return null;
  if (isLoading) {
    return (
      <div className="border-t border-border/30 bg-muted/10 px-3 py-2 text-label text-muted-foreground">
        {t("fumenRowDetail.loading")}
      </div>
    );
  }
  if (isError || !data) return null;

  return (
    <div className="border-t border-border/30 bg-muted/10">
      {data.records.length === 0 && (
        <div className="px-3 py-2 text-label text-muted-foreground">{t("fumenRowDetail.noRecords")}</div>
      )}
      <div className="flex flex-wrap justify-center divide-x divide-border/30">
        {data.records.map((record) => (
          <CourseRecordCard key={record.score_id} record={record} />
        ))}
      </div>
      <CourseStagesSection stages={data.stages} />
    </div>
  );
}

// ── Course stages section ─────────────────────────────────────────────────────

import type { CourseStage } from "@/lib/score-row-detail-types";

function CourseStagesSection({ stages }: { stages: CourseStage[] }) {
  const { t } = useTranslation();
  return (
    <div className="px-3 py-2 border-t border-border/30">
      <p className="text-caption text-muted-foreground/70 uppercase tracking-widest mb-2">
        {t("fumenRowDetail.stages")}
      </p>
      <div className="space-y-1">
        {stages.map((stage) => {
          const hash = stage.fumen_sha256 ?? stage.fumen_md5;
          const levelStr = stage.level
            ? (stage.table_symbol
                ? `${stage.table_symbol}${stage.level.replace(stage.table_symbol, "")}`
                : stage.level)
            : "--";
          return (
            <div key={stage.stage} className="flex items-baseline gap-2 text-label">
              <span className="w-14 shrink-0 text-caption text-muted-foreground/60 tabular-nums">
                STAGE {stage.stage}
              </span>
              <span className="w-12 shrink-0 text-caption tabular-nums text-muted-foreground">
                {levelStr}
              </span>
              {hash && stage.title ? (
                <Link
                  href={`/songs/${encodeURIComponent(hash)}`}
                  className="truncate hover:text-primary transition-colors"
                >
                  {stage.title}
                </Link>
              ) : (
                <span className={cn("truncate", !stage.title && "text-muted-foreground")}>
                  {stage.title ?? t("fumenRowDetail.unknownStage")}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── History row detail (song page) ────────────────────────────────────────────

/** Render song-history detail from an already enriched API row. */
export function FumenHistoryRowDetail({ score }: { score: UserScore }) {
  const record: RowDetailRecord = {
    score_id: score.id,
    client_type: score.client_type,
    clear_type: score.clear_type,
    min_bp: score.min_bp,
    rate: score.rate,
    rank: score.rank,
    exscore: score.exscore,
    play_count: score.play_count,
    judgment_detail: score.judgment_detail,
    arrangement: score.arrangement,
  };

  if (record.judgment_detail === null && record.arrangement === null) return null;

  return (
    <div className="border-t border-border/30 bg-muted/10">
      <RecordCard record={record} keymode={null} />
    </div>
  );
}
