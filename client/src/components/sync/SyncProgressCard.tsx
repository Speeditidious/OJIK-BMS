import { ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";

import { formatNumber } from "../../lib/format";
import type { ClientType, SyncProgressEvent, SyncStage } from "../../types";

const STAGE_ORDER: SyncStage[] = ["validating", "parsing", "supplementing", "uploading", "finalizing", "done"];

const CLIENT_LABEL: Record<ClientType, string> = {
  lr2: "LR2",
  beatoraja: "beatoraja",
};

export interface SyncProgressCardProps {
  stage: SyncStage | null;
  progress: { global?: SyncProgressEvent; lr2?: SyncProgressEvent; beatoraja?: SyncProgressEvent };
  ticker?: string | null;
}

export function SyncProgressCard({ stage, progress, ticker }: SyncProgressCardProps) {
  const { t } = useTranslation();
  const stageIndex = stage ? STAGE_ORDER.indexOf(stage) : -1;
  const lanes: Array<{ key: "global" | ClientType; label: string; ev?: SyncProgressEvent }> = [];

  // Client-specific lanes are only meaningful during the parsing stage.
  // In all other stages (uploading, supplementing, ...) the global lane carries
  // the actual batch progress (current / total), so we show that instead.
  if (stage === "parsing") {
    if (progress.lr2) lanes.push({ key: "lr2", label: CLIENT_LABEL.lr2, ev: progress.lr2 });
    if (progress.beatoraja) lanes.push({ key: "beatoraja", label: CLIENT_LABEL.beatoraja, ev: progress.beatoraja });
  }
  if (lanes.length === 0) {
    lanes.push({ key: "global", label: t("client.sync.progress.global"), ev: progress.global });
  }

  return (
    <div className="sync-progress" aria-live="polite">
      <div className="sync-stage-chips" role="list" aria-label={t("client.sync.progress.ariaLabel")}>
        {STAGE_ORDER.filter((s) => s !== "done").map((s, idx) => {
          const isActive = stage === s;
          const isDone = stageIndex > idx;
          const stageKey = `client.sync.progress.stages.${s}` as const;
          return (
            <span
              key={s}
              role="listitem"
              className={`sync-stage-chip${isActive ? " is-active" : ""}${isDone ? " is-done" : ""}`}
            >
              {t(stageKey)}
              {idx < STAGE_ORDER.length - 2 ? (
                <ChevronRight size={12} className="sync-stage-arrow" aria-hidden="true" />
              ) : null}
            </span>
          );
        })}
      </div>

      <div className="sync-lanes">
        {lanes.map((lane) => (
          <Lane key={lane.key} label={lane.label} ev={lane.ev} />
        ))}
      </div>

      <div className="sync-ticker">{ticker ?? t("client.sync.progress.idleTicker")}</div>
    </div>
  );
}

function Lane({ label, ev }: { label: string; ev?: SyncProgressEvent }) {
  const { t } = useTranslation();
  const total = ev?.total ?? null;
  const current = ev?.current ?? 0;
  const indeterminate = !total || total <= 0;
  const pct = indeterminate ? 0 : Math.min(100, Math.max(0, (current / total) * 100));

  return (
    <div className="sync-lane">
      <span className="sync-lane-label">{label}</span>
      <div className={`sync-bar${indeterminate ? " is-indeterminate" : ""}`}>
        <span className="sync-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="sync-lane-count">
        {indeterminate
          ? ev?.message ?? t("client.sync.progress.preparing")
          : `${formatNumber(current)} / ${formatNumber(total!)}`}
      </span>
    </div>
  );
}
