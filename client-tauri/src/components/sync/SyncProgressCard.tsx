import { ChevronRight } from "lucide-react";

import { formatNumber } from "../../lib/format";
import type { ClientType, SyncProgressEvent, SyncStage } from "../../types";

const STAGE_ORDER: SyncStage[] = ["validating", "parsing", "supplementing", "uploading", "finalizing", "done"];

const STAGE_LABEL: Record<SyncStage, string> = {
  validating: "파일 검증",
  parsing: "파싱",
  supplementing: "해시 보강",
  uploading: "업로드",
  finalizing: "마무리",
  done: "완료",
};

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
  const stageIndex = stage ? STAGE_ORDER.indexOf(stage) : -1;
  const lanes: Array<{ key: "global" | ClientType; label: string; ev?: SyncProgressEvent }> = [];

  if (progress.lr2) lanes.push({ key: "lr2", label: CLIENT_LABEL.lr2, ev: progress.lr2 });
  if (progress.beatoraja) lanes.push({ key: "beatoraja", label: CLIENT_LABEL.beatoraja, ev: progress.beatoraja });
  if (lanes.length === 0) {
    lanes.push({ key: "global", label: "전체", ev: progress.global });
  }

  return (
    <div className="sync-progress" aria-live="polite">
      <div className="sync-stage-chips" role="list" aria-label="동기화 단계">
        {STAGE_ORDER.filter((s) => s !== "done").map((s, idx) => {
          const isActive = stage === s;
          const isDone = stageIndex > idx;
          return (
            <span
              key={s}
              role="listitem"
              className={`sync-stage-chip${isActive ? " is-active" : ""}${isDone ? " is-done" : ""}`}
            >
              {STAGE_LABEL[s]}
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

      <div className="sync-ticker">{ticker ?? "동기화 진행 상황이 여기에 표시됩니다."}</div>
    </div>
  );
}

function Lane({ label, ev }: { label: string; ev?: SyncProgressEvent }) {
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
          ? ev?.message ?? "준비 중…"
          : `${formatNumber(current)} / ${formatNumber(total!)}`}
      </span>
    </div>
  );
}
