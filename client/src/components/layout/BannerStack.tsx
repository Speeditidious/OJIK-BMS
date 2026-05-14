import { AlertTriangle, ShieldAlert, Download } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { AuthStatus, ClientConfig, UpdatePolicy } from "../../types";
import { Button } from "../primitives/Button";

export interface BannerStackProps {
  auth: AuthStatus | null;
  config: ClientConfig | null;
  policy: UpdatePolicy | null;
  syncRunning: boolean;
  sessionExpired?: boolean;
  onLogin: () => void;
  onInstallUpdate: () => void;
  onOpenDownloadPage: () => void;
  onClearUpdateFailure: () => void;
}

export function BannerStack({
  auth,
  config,
  policy,
  syncRunning,
  sessionExpired = false,
  onLogin,
  onInstallUpdate,
  onOpenDownloadPage,
  onClearUpdateFailure,
}: BannerStackProps) {
  const { t } = useTranslation();

  if (syncRunning) return null;

  const banners: React.ReactNode[] = [];

  if (policy?.update_available && policy.announcement?.mandatory) {
    banners.push(
      <div className="banner banner-danger" key="mandatory">
        <ShieldAlert size={18} aria-hidden="true" />
        <div>
          <div className="banner-title">{t("client.banners.mandatoryUpdate")} {policy.announcement.version}</div>
          <div className="banner-body">{policy.announcement.title}</div>
        </div>
        <div className="banner-actions">
          <Button variant="primary" size="sm" onClick={onInstallUpdate}>
            {t("client.banners.updateNow")}
          </Button>
        </div>
      </div>,
    );
  }

  const days = auth?.refresh_token_expire_days ?? null;
  if (auth && !auth.logged_in) {
    const isExpired = sessionExpired;
    banners.push(
      <div className="banner banner-warn" key="login-needed">
        <AlertTriangle size={18} aria-hidden="true" />
        <div>
          <div className="banner-title">
            {isExpired
              ? t("client.banners.loginExpiredTitle")
              : t("client.banners.loginRequiredTitle")}
          </div>
          <div className="banner-body">
            {isExpired
              ? t("client.banners.loginExpiredBody")
              : t("client.banners.loginRequiredBody")}
          </div>
        </div>
        <div className="banner-actions">
          <Button variant="primary" size="sm" onClick={onLogin}>
            {isExpired ? t("client.banners.relogin") : t("client.banners.loginNow")}
          </Button>
        </div>
      </div>,
    );
  } else if (auth?.logged_in && typeof days === "number" && days <= 3) {
    banners.push(
      <div className="banner banner-warn" key="expiring">
        <AlertTriangle size={18} aria-hidden="true" />
        <div>
          <div className="banner-title">{t("client.banners.sessionExpiring", { days: Math.max(0, days) })}</div>
          <div className="banner-body">{t("client.banners.sessionExpiringBody")}</div>
        </div>
        <div className="banner-actions">
          <Button variant="primary" size="sm" onClick={onLogin}>
            {t("client.banners.relogin")}
          </Button>
        </div>
      </div>,
    );
  }

  if (config?.last_update_failure_at && config?.last_update_failure_message) {
    banners.push(
      <div className="banner banner-warn" key="update-failure">
        <Download size={18} aria-hidden="true" />
        <div>
          <div className="banner-title">
            {t("client.banners.previousUpdateFailed")}
            {config.last_update_failure_version ? ` (${config.last_update_failure_version})` : ""}
          </div>
          <div className="banner-body">{config.last_update_failure_message}</div>
        </div>
        <div className="banner-actions">
          <Button variant="default" size="sm" onClick={onOpenDownloadPage}>
            {t("client.banners.openDownload")}
          </Button>
          <Button variant="ghost" size="sm" onClick={onClearUpdateFailure}>
            {t("client.banners.dismiss")}
          </Button>
        </div>
      </div>,
    );
  }

  if (banners.length === 0) return null;
  return <div className="banner-stack">{banners}</div>;
}
