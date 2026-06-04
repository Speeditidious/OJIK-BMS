import { Database, Download, Loader2, RefreshCw, Sparkles, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { formatLocalizedDateTime, formatNumber, formatRelativeTime } from "../../lib/format";
import type { ClientConfig, SyncResult } from "../../types";
import { Button } from "../primitives/Button";
import { Tooltip } from "../primitives/Tooltip";

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
  const { t } = useTranslation();
  const lastResultErrorCount = lastResult?.errors.filter((e) => e.level !== "warn").length ?? 0;
  const lastSyncedAt = lastResultErrorCount > 0
    ? config.last_synced_at
    : lastResult?.finished_at ?? config.last_synced_at;
  // Quick Sync only makes sense once a full sync has populated chart metadata,
  // so hide it until the user has at least one sync on record.
  const hasSyncHistory = Boolean(lastSyncedAt);

  return (
    <section className="sync-hero" aria-label={t("client.sync.hero.ariaLabel")}>
      <div className="sync-hero-info">
        <div className="sync-hero-eyebrow">
          {syncRunning ? (
            <>
              <Loader2 size={12} className="spin" aria-hidden="true" />
              {t("client.sync.hero.running")}
            </>
          ) : (
            <>
              <Sparkles size={12} aria-hidden="true" />
              {t("client.sync.hero.syncNow")}
            </>
          )}
        </div>

        {lastSyncedAt ? (
          <>
            <h2 className="sync-hero-title">{t("client.sync.hero.lastSync")} {formatRelativeTime(lastSyncedAt, t)}</h2>
            <div className="sync-hero-meta">
              <span title={lastSyncedAt}>{formatLocalizedDateTime(lastSyncedAt, t)}</span>
              {lastResult && lastResultErrorCount === 0 ? (
                <>
                  <span>
                    {t("client.sync.hero.inserted")} <b>{formatNumber(lastResult.inserted)}</b>
                  </span>
                  <span>
                    {t("client.sync.hero.updated")} <b>{formatNumber(lastResult.metadata_updated)}</b>
                  </span>
                </>
              ) : null}
              {lastResultErrorCount > 0 ? (
                <span style={{ color: "var(--danger)" }}>
                  {t("client.sync.hero.recentErrors")} <b>{formatNumber(lastResultErrorCount)}</b>
                </span>
              ) : null}
            </div>
          </>
        ) : (
          <>
            <h2 className="sync-hero-title">{t("client.sync.hero.neverSyncedTitle")}</h2>
            <div className="sync-hero-meta">
              {t("client.sync.hero.neverSyncedBody")}
            </div>
          </>
        )}
      </div>

      <div className="sync-hero-actions">
        {syncRunning ? (
          <Button variant="danger" size="lg" leadingIcon={<X size={16} aria-hidden="true" />} onClick={onCancel}>
            {t("client.sync.hero.cancel")}
          </Button>
        ) : (
          <>
            {hasSyncHistory ? (
              <Tooltip text={t("client.sync.hero.quickHint")}>
                <Button
                  variant="primary"
                  size="lg"
                  leadingIcon={<Database size={16} aria-hidden="true" />}
                  onClick={onQuickSync}
                  disabled={syncDisabled}
                  title={syncDisabledReason}
                >
                  {t("client.sync.hero.quick")}
                </Button>
              </Tooltip>
            ) : null}
            <Tooltip text={t("client.sync.hero.fullHint")}>
              <Button
                variant="accent"
                size="lg"
                leadingIcon={<Download size={16} aria-hidden="true" />}
                onClick={onFullSync}
                disabled={syncDisabled}
                title={syncDisabledReason}
              >
                {t("client.sync.hero.full")}
              </Button>
            </Tooltip>
          </>
        )}
      </div>
    </section>
  );
}

export function SyncStubNotice({ message }: { message: string }) {
  const { t } = useTranslation();
  return (
    <div className="stub-card" role="status">
      <RefreshCw size={16} aria-hidden="true" />
      <div>
        <div className="stub-card-title">{t("client.sync.hero.enginePending")}</div>
        <div className="stub-card-body">{message}</div>
      </div>
    </div>
  );
}
