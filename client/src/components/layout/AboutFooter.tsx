import { Download, ExternalLink, FileText } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "../primitives/Button";

export function AboutFooter({
  version,
  channel,
  onOpenDownloadPage,
  onOpenSite,
  onOpenLogFile,
}: {
  version: string;
  channel: string;
  onOpenDownloadPage: () => void;
  onOpenSite: () => void;
  onOpenLogFile?: () => void;
}) {
  const { t } = useTranslation();

  return (
    <footer className="about-footer">
      <div className="about-meta">
        <span>
          <b>{t("client.footer.version")}</b> v{version}
        </span>
        <span>
          <b>{t("client.footer.channel")}</b> {channel}
        </span>
      </div>
      <div className="about-actions">
        {onOpenLogFile ? (
          <Button variant="ghost" size="sm" leadingIcon={<FileText size={14} aria-hidden="true" />} onClick={onOpenLogFile}>
            {t("client.footer.logFile")}
          </Button>
        ) : null}
        <Button
          variant="ghost"
          size="sm"
          leadingIcon={<ExternalLink size={14} aria-hidden="true" />}
          onClick={onOpenSite}
        >
          {t("client.footer.openSite")}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          leadingIcon={<Download size={14} aria-hidden="true" />}
          onClick={onOpenDownloadPage}
        >
          {t("client.footer.downloadPage")}
        </Button>
      </div>
    </footer>
  );
}
