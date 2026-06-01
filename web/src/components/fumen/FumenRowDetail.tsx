"use client";

import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import { useScoreRowDetail } from "@/hooks/use-score-row-detail";
import { UnavailableValue } from "@/components/common/UnavailableValue";
import {
  JUDGMENT_STYLE,
  arrangementOptionLabel,
  laneIsWhiteKey,
} from "@/lib/score-row-detail-core.mjs";
import type { RowDetailRecord, LaneGroup } from "@/lib/score-row-detail-types";

const JUDGMENT_BG: Record<string, string> = {
  pgreat: "bg-emerald-400/10 border-emerald-400/30",
  great:  "bg-blue-400/10 border-blue-400/30",
  good:   "bg-orange-400/10 border-orange-400/30",
  bad:    "bg-red-400/10 border-red-400/30",
  poor:   "bg-purple-400/10 border-purple-400/30",
  miss:   "bg-gray-400/10 border-gray-400/30",
};

function JudgmentSection({ record }: { record: RowDetailRecord }) {
  const { t } = useTranslation();
  const detail = record.judgment_detail;
  if (!detail) return null;
  const isBeatoraja = record.client_type === "beatoraja";

  return (
    <div className="space-y-1.5">
      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
        {t("fumenRowDetail.judgments")}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {detail.judgments.map((jg) => {
          const style = JUDGMENT_STYLE[jg.key] ?? { color: "text-foreground" };
          const bgStyle = JUDGMENT_BG[jg.key] ?? "bg-muted/30 border-border/50";
          const label = jg.key === "pgreat" ? "PG" : jg.key.charAt(0).toUpperCase() + jg.key.slice(1);
          return (
            <div
              key={jg.key}
              className={cn(
                "flex flex-col items-center rounded-md px-2 py-1 border",
                bgStyle,
              )}
            >
              <span className={cn("text-[9px] font-bold uppercase tracking-wide", style.color)}>
                {label}
              </span>
              <span className="text-xs font-mono font-semibold text-foreground tabular-nums">
                {jg.count.toLocaleString()}
              </span>
              {isBeatoraja && jg.fast !== null && jg.slow !== null && (
                <div className="flex gap-1.5 mt-0.5">
                  <span className="text-[9px] font-mono text-blue-400 tabular-nums">{jg.fast}</span>
                  <span className="text-[9px] font-mono text-red-400 tabular-nums">{jg.slow}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
      {isBeatoraja && (
        detail.fast_total_excluding_pgreat !== null ||
        detail.slow_total_excluding_pgreat !== null
      ) && (
        <div className="flex gap-3 pt-0.5">
          {detail.fast_total_excluding_pgreat !== null && (
            <span className="text-[10px] text-blue-400">
              {t("fumenRowDetail.fastTotalExPgreat")}: <span className="font-mono font-semibold">{detail.fast_total_excluding_pgreat.toLocaleString()}</span>
            </span>
          )}
          {detail.slow_total_excluding_pgreat !== null && (
            <span className="text-[10px] text-red-400">
              {t("fumenRowDetail.slowTotalExPgreat")}: <span className="font-mono font-semibold">{detail.slow_total_excluding_pgreat.toLocaleString()}</span>
            </span>
          )}
        </div>
      )}
    </div>
  );
}

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
        <span className="text-[9px] font-bold text-muted-foreground uppercase tracking-wider">
          {label}
        </span>
      )}
      <div className="flex gap-0.5">
        {group.lanes.map((lane, idx) => {
          const isWhite = keymode !== null
            ? laneIsWhiteKey(keymode, lane)
            : idx % 2 === 0;
          return (
            <div
              key={idx}
              className={cn(
                "flex items-center justify-center rounded-sm text-[9px] font-mono font-semibold select-none border",
                "w-6 h-10",
                isWhite
                  ? "bg-white/20 border-white/40 text-white/90"
                  : "bg-zinc-900/60 border-white/10 text-white/50",
              )}
            >
              {lane}
            </div>
          );
        })}
      </div>
      {group.option_label && (
        <span className="text-[9px] text-muted-foreground font-mono">
          {group.option_label}
        </span>
      )}
    </div>
  );
}

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

  const optionLabel = arrangementOptionLabel(arr.option_label);
  const isUnavailable = arr.unavailable_reason !== null || arr.lane_groups === null;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1.5">
        <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
          {t("fumenRowDetail.arrangement")}
        </p>
        <span className="text-[10px] font-mono text-foreground/60 bg-muted/50 px-1.5 py-0 rounded border border-border/30">
          {optionLabel}
        </span>
        {arr.double_option_label && (
          <span className="text-[10px] font-mono text-accent/70 bg-accent/10 px-1.5 py-0 rounded border border-accent/20">
            {arr.double_option_label}
          </span>
        )}
      </div>
      {isUnavailable ? (
        <UnavailableValue reason={arr.unavailable_reason} />
      ) : (
        <div className="flex gap-3">
          {arr.lane_groups!.map((group, idx) => {
            const isDP = arr.lane_groups!.length > 1;
            const sideLabel = isDP
              ? (group.side === "1p" ? "1P" : group.side === "2p" ? "2P" : group.side.toUpperCase())
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

function ClientLabel({ clientType }: { clientType: string }) {
  const { t } = useTranslation();
  const label = clientType === "lr2"
    ? t("fumenRowDetail.client.lr2")
    : clientType === "beatoraja"
    ? t("fumenRowDetail.client.beatoraja")
    : clientType.toUpperCase();
  const colorClass = clientType === "lr2"
    ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
    : clientType === "beatoraja"
    ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/30"
    : "bg-muted/50 text-muted-foreground border-border/50";

  return (
    <span className={cn(
      "inline-flex items-center px-1.5 py-0 rounded text-[9px] font-bold uppercase tracking-wider border",
      colorClass,
    )}>
      {label}
    </span>
  );
}

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
    <div className="flex flex-wrap gap-4 p-3 rounded-lg bg-muted/20 border border-border/40">
      <div className="flex items-start pt-0.5">
        <ClientLabel clientType={record.client_type} />
      </div>
      <div className="flex flex-wrap gap-4 min-w-0">
        {hasJudgments && <JudgmentSection record={record} />}
        {hasArrangement && <ArrangementSection record={record} keymode={keymode} />}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface FumenRowDetailProps {
  fumenId: string | null | undefined;
  userId?: string | null;
  asOf?: string | null;
}

/**
 * Expanded-row detail panel for a fumen in a table or song list.
 * Lazy-fetches judgment and arrangement details on mount.
 */
export function FumenRowDetail({ fumenId, userId, asOf }: FumenRowDetailProps) {
  const { t } = useTranslation();
  const { data, isLoading, isError } = useScoreRowDetail({
    fumenId,
    userId,
    asOf,
    enabled: !!fumenId,
  });

  if (!fumenId) return null;

  if (isLoading) {
    return (
      <div className="px-3 py-2 text-[11px] text-muted-foreground">
        {t("fumenRowDetail.loading")}
      </div>
    );
  }

  if (isError || !data) return null;

  if (data.records.length === 0) {
    return (
      <div className="px-3 py-2 text-[11px] text-muted-foreground">
        {t("fumenRowDetail.noRecords")}
      </div>
    );
  }

  const hasContent = data.records.some(
    (r) => r.judgment_detail !== null || r.arrangement !== null
  );
  if (!hasContent) return null;

  return (
    <div className="px-3 py-2 space-y-2">
      {data.records.map((record) => (
        <RecordCard key={record.score_id} record={record} keymode={data.keymode} />
      ))}
    </div>
  );
}
