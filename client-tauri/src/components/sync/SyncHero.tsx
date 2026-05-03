import { Database, Download, Loader2, RefreshCw, Sparkles, X } from "lucide-react";

import { formatKoreanDateTime, formatNumber, formatRelativeTime } from "../../lib/format";
import type { ClientConfig, SyncResult } from "../../types";
import { Button } from "../primitives/Button";

export interface SyncHeroProps {
  config: ClientConfig;
  lastResult: SyncResult | null;
  syncRunning: boolean;
  syncDisabled: boolean;
  syncDisabledReason?: string;
  onQuickSync: () => void;
  onFullSync: () => void;
  onCancel: () => void;
}

export function SyncHero({
  config,
  lastResult,
  syncRunning,
  syncDisabled,
  syncDisabledReason,
  onQuickSync,
  onFullSync,
  onCancel,
}: SyncHeroProps) {
  const lastSyncedAt = lastResult?.finished_at ?? config.last_synced_at;

  return (
    <section className="sync-hero" aria-label="동기화">
      <div className="sync-hero-info">
        <div className="sync-hero-eyebrow">
          {syncRunning ? (
            <>
              <Loader2 size={12} className="spin" aria-hidden="true" />
              동기화 진행 중
            </>
          ) : (
            <>
              <Sparkles size={12} aria-hidden="true" />
              지금 동기화
            </>
          )}
        </div>

        {lastSyncedAt ? (
          <>
            <h2 className="sync-hero-title">마지막 동기화 {formatRelativeTime(lastSyncedAt)}</h2>
            <div className="sync-hero-meta">
              <span title={lastSyncedAt}>{formatKoreanDateTime(lastSyncedAt)}</span>
              {lastResult ? (
                <>
                  <span>
                    등록된 기록 <b>{formatNumber(lastResult.inserted)}</b>건
                  </span>
                  <span>
                    수정된 기록 <b>{formatNumber(lastResult.metadata_updated)}</b>건
                  </span>
                  {lastResult.errors.length > 0 ? (
                    <span style={{ color: "var(--danger)" }}>
                      오류 <b>{formatNumber(lastResult.errors.length)}</b>건
                    </span>
                  ) : null}
                </>
              ) : null}
            </div>
          </>
        ) : (
          <>
            <h2 className="sync-hero-title">아직 동기화한 적이 없어요</h2>
            <div className="sync-hero-meta">
              경로를 채우고 첫 동기화를 시작해 보세요. 곡 메타까지 함께 보내려면 전체 동기화를 사용하세요.
            </div>
          </>
        )}
      </div>

      <div className="sync-hero-actions">
        {syncRunning ? (
          <Button variant="danger" size="lg" leadingIcon={<X size={16} aria-hidden="true" />} onClick={onCancel}>
            동기화 취소
          </Button>
        ) : (
          <>
            <Button
              variant="primary"
              size="lg"
              leadingIcon={<Database size={16} aria-hidden="true" />}
              onClick={onQuickSync}
              disabled={syncDisabled}
              title={syncDisabledReason}
            >
              빠른 동기화
            </Button>
            <Button
              variant="accent"
              size="lg"
              leadingIcon={<Download size={16} aria-hidden="true" />}
              onClick={onFullSync}
              disabled={syncDisabled}
              title={syncDisabledReason}
            >
              전체 동기화
            </Button>
          </>
        )}
      </div>
    </section>
  );
}

export function SyncStubNotice({ message }: { message: string }) {
  return (
    <div className="stub-card" role="status">
      <RefreshCw size={16} aria-hidden="true" />
      <div>
        <div className="stub-card-title">동기화 엔진은 곧 연결됩니다</div>
        <div className="stub-card-body">{message}</div>
      </div>
    </div>
  );
}
