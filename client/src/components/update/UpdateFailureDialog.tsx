import { AlertTriangle, Download, RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { UpdateError } from "../../types";
import { Button } from "../primitives/Button";
import { Dialog } from "../primitives/Dialog";

export function UpdateFailureDialog({
  open,
  error,
  mandatory,
  onRetry,
  onOpenDownloadPage,
  onClose,
}: {
  open: boolean;
  error: UpdateError;
  mandatory: boolean;
  onRetry: () => void;
  onOpenDownloadPage: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();

  const stageKey = `client.updates.stages.${error.stage}` as const;
  const stageLabel = t(stageKey, { defaultValue: error.stage });

  return (
    <Dialog
      open={open}
      onClose={onClose}
      dismissable={!mandatory}
      title={
        <span style={{ color: "var(--danger)", display: "inline-flex", alignItems: "center", gap: 6 }}>
          <AlertTriangle size={16} aria-hidden="true" />
          {t("client.updates.failureTitle")}
        </span>
      }
      footer={
        <>
          {!mandatory ? (
            <Button variant="ghost" onClick={onClose}>
              {t("client.updates.close")}
            </Button>
          ) : null}
          <Button
            variant="default"
            leadingIcon={<Download size={14} aria-hidden="true" />}
            onClick={onOpenDownloadPage}
          >
            {t("client.updates.openDownload")}
          </Button>
          <Button
            variant="primary"
            leadingIcon={<RefreshCw size={14} aria-hidden="true" />}
            onClick={onRetry}
          >
            {t("client.updates.retry")}
          </Button>
        </>
      }
    >
      <div style={{ display: "grid", gap: 10 }}>
        <div style={{ color: "var(--muted)", fontSize: "0.86rem" }}>
          {t("client.updates.stage")}: <b style={{ color: "var(--text)" }}>{stageLabel}</b>
        </div>
        <pre
          style={{
            color: "var(--danger)",
            background: "var(--surface-2)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: 12,
            fontSize: "0.84rem",
            maxHeight: 200,
            overflowY: "auto",
            margin: 0,
            whiteSpace: "pre-wrap",
          }}
        >
          {error.message}
        </pre>
        {mandatory ? (
          <div className="banner banner-warn">
            <div>
              <div className="banner-title">{t("client.updates.failureMandatoryTitle")}</div>
              <div className="banner-body">
                {t("client.updates.failureMandatoryBody")}
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </Dialog>
  );
}
