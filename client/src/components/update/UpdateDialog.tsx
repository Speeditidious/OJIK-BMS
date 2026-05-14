import { Download, ExternalLink } from "lucide-react";
import { useTranslation } from "react-i18next";

import { formatBytes } from "../../lib/format";
import { selectAnnouncementBody } from "../../lib/update-announcement";
import type { LanguageCode, UpdateAnnouncement } from "../../types";
import { Button } from "../primitives/Button";
import { Dialog } from "../primitives/Dialog";

export interface UpdateDialogProps {
  open: boolean;
  announcement: UpdateAnnouncement;
  isInstalling: boolean;
  downloadProgress?: { downloaded: number; total?: number | null } | null;
  supportsAutoInstall: boolean;
  onInstall: () => void;
  onLater?: () => void;
  onSkip?: () => void;
  onOpenReleasePage?: (url: string) => void;
  onClose?: () => void;
}

export function UpdateDialog({
  open,
  announcement,
  isInstalling,
  downloadProgress,
  supportsAutoInstall,
  onInstall,
  onLater,
  onSkip,
  onOpenReleasePage,
  onClose,
}: UpdateDialogProps) {
  const { i18n, t } = useTranslation();
  const mandatory = announcement.mandatory;
  const dismissable = !mandatory;
  const language = (i18n.language?.split("-")[0] ?? "ko") as LanguageCode;
  const bodyMarkdown = selectAnnouncementBody(announcement, language);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      dismissable={dismissable}
      closeOnBackdrop={dismissable}
      title={
        <span>
          {mandatory ? t("client.updates.mandatoryDialogTitle") : t("client.updates.dialogTitle")} ·{" "}
          <span style={{ color: "var(--muted)" }}>v{announcement.version}</span>
        </span>
      }
      footer={
        <>
          {announcement.release_page_url ? (
            <Button
              variant="ghost"
              leadingIcon={<ExternalLink size={14} aria-hidden="true" />}
              onClick={() => onOpenReleasePage?.(announcement.release_page_url!)}
            >
              {t("client.updates.openDownload")}
            </Button>
          ) : null}
          {!mandatory ? (
            <>
              {onSkip ? (
                <Button variant="ghost" onClick={onSkip}>
                  {t("client.updates.skipVersion")}
                </Button>
              ) : null}
              {onLater ? (
                <Button variant="default" onClick={onLater}>
                  {t("client.updates.later")}
                </Button>
              ) : null}
            </>
          ) : null}
          <Button
            variant="primary"
            leadingIcon={<Download size={14} aria-hidden="true" />}
            onClick={onInstall}
            disabled={isInstalling}
          >
            {isInstalling
              ? t("client.updates.installing")
              : supportsAutoInstall
                ? t("client.updates.installNow")
                : t("client.updates.downloadInstaller")}
          </Button>
        </>
      }
    >
      <div style={{ display: "grid", gap: 12 }}>
        <h2 style={{ fontSize: "1.05rem" }}>{announcement.title}</h2>

        <div style={{ display: "flex", gap: 14, color: "var(--muted)", fontSize: "0.84rem", flexWrap: "wrap" }}>
          {announcement.asset_size_bytes ? (
            <span>{t("client.updates.downloadSize")}: <b style={{ color: "var(--text)" }}>{formatBytes(announcement.asset_size_bytes)}</b></span>
          ) : null}
          {announcement.published_at ? (
            <span>{t("client.updates.publishedAt")}: <b style={{ color: "var(--text)" }}>{new Date(announcement.published_at).toLocaleDateString()}</b></span>
          ) : null}
        </div>

        <pre
          style={{
            color: "var(--text)",
            background: "var(--surface-2)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: 12,
            fontSize: "0.86rem",
            maxHeight: 220,
            overflowY: "auto",
            margin: 0,
            fontFamily: '"Segoe UI", "Malgun Gothic", "Noto Sans KR", system-ui, sans-serif',
            whiteSpace: "pre-wrap",
          }}
        >
          {bodyMarkdown}
        </pre>

        {downloadProgress ? (
          <DownloadProgress downloaded={downloadProgress.downloaded} total={downloadProgress.total ?? null} />
        ) : null}

        {!supportsAutoInstall ? (
          <div className="banner banner-info">
            <div>
              <div className="banner-body">
                {t("client.updates.manualInstallerHint")}
              </div>
            </div>
          </div>
        ) : null}

        {mandatory ? (
          <div className="banner banner-warn">
            <div>
              <div className="banner-title">{t("client.updates.mandatoryBlocked")}</div>
              <div className="banner-body">
                {t("client.updates.mandatoryBody")}
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </Dialog>
  );
}

function DownloadProgress({ downloaded, total }: { downloaded: number; total: number | null }) {
  const { t } = useTranslation();
  const indeterminate = !total || total <= 0;
  const pct = indeterminate ? 0 : Math.min(100, (downloaded / total) * 100);
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <div className={`sync-bar${indeterminate ? " is-indeterminate" : ""}`} style={{ height: 8 }}>
        <span className="sync-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span style={{ color: "var(--muted)", fontSize: "0.78rem" }}>
        {indeterminate ? t("client.updates.downloading") : `${formatBytes(downloaded)} / ${formatBytes(total)}`}
      </span>
    </div>
  );
}
