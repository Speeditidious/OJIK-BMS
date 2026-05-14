import { ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { formatNumber, formatRelativeTime } from "../../lib/format";
import type { SyncResult } from "../../types";
import { Button } from "../primitives/Button";

export interface ResultSummaryProps {
  result: SyncResult | null;
  onOpenResultUrl?: (url: string) => void;
  onJumpToLog?: () => void;
}

export function ResultSummary({ result, onOpenResultUrl, onJumpToLog }: ResultSummaryProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  // Auto-expand once when a fresh result arrives.
  useEffect(() => {
    if (result) setOpen(true);
  }, [result]);

  if (!result) return null;

  const errorCount = result.errors.filter((e) => e.level !== "warn").length;
  const resultUrl = result.result_url ?? "https://www.ojikbms.kr/dashboard";

  return (
    <section className="card fade-in" aria-label={t("client.sync.result.ariaLabel")}>
      <header className="card-hd">
        <div className="card-title">
          {t("client.sync.result.title")}
          <span style={{ color: "var(--muted)", fontWeight: 400, marginLeft: 8 }}>
            {formatRelativeTime(result.finished_at, t)}
          </span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          leadingIcon={open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? t("client.sync.result.collapse") : t("client.sync.result.expand")}
        </Button>
      </header>

      {open ? (
        <div className="card-bd">
          <div className="result-stats">
            <div className="result-stat result-stat-new">
              <span className="result-stat-label">{t("client.sync.result.inserted")}</span>
              <span className="result-stat-value">
                <b>{formatNumber(result.inserted)}</b>
              </span>
            </div>
            <div className="result-stat result-stat-improved">
              <span className="result-stat-label">{t("client.sync.result.updated")}</span>
              <span className="result-stat-value">
                <b>{formatNumber(result.metadata_updated)}</b>
              </span>
            </div>
            <div className="result-stat result-stat-error">
              <span className="result-stat-label">{t("client.sync.result.errors")}</span>
              <span className="result-stat-value">
                <b>{formatNumber(errorCount)}</b>
              </span>
            </div>
          </div>

          {errorCount > 0 ? (
            <div className="result-extra">
              <strong style={{ color: "var(--danger)" }}>{t("client.sync.result.errors")} {formatNumber(errorCount)}</strong>
              <ul>
                {result.errors.slice(0, 5).map((err, idx) => (
                  <li key={idx}>
                    {err.client ? `[${err.client}] ` : ""}
                    {err.message}
                  </li>
                ))}
                {errorCount > 5 ? (
                  <li>
                    {t("client.sync.result.moreErrors", { count: errorCount - 5 })} —{" "}
                    <button type="button" className="btn btn-ghost btn-sm" onClick={onJumpToLog}>
                      {t("client.sync.result.viewInLogs")}
                    </button>
                  </li>
                ) : null}
              </ul>
            </div>
          ) : null}

          <div className="result-cta">
            <span style={{ color: "var(--muted)", fontSize: "0.84rem" }}>
              {t("client.sync.result.siteHint")}
            </span>
            <Button
              variant="primary"
              leadingIcon={<ExternalLink size={14} aria-hidden="true" />}
              onClick={() => onOpenResultUrl?.(resultUrl)}
            >
              {t("client.sync.result.openSite")}
            </Button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
