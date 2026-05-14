import { ExternalLink, Info, LogIn, LogOut } from "lucide-react";
import { useTranslation } from "react-i18next";

import logoUrl from "../../assets/ojikbms_logo.png";
import type { AuthStatus, LanguageCode } from "../../types";
import { AuthPill } from "../auth/AuthPill";
import { LanguageMenu } from "../language/LanguageMenu";
import { Button } from "../primitives/Button";

export function Topbar({
  auth,
  onLogin,
  onLogout,
  onOpenDiagnostics,
  onOpenSite,
  isLoggingIn,
  language,
  onLanguageChange,
}: {
  auth: AuthStatus | null;
  onLogin: () => void;
  onLogout: () => void;
  onOpenDiagnostics: () => void;
  onOpenSite: () => void;
  isLoggingIn: boolean;
  language: LanguageCode;
  onLanguageChange: (language: LanguageCode) => void;
}) {
  const { t } = useTranslation();

  return (
    <header className="topbar">
      <div className="topbar-brand">
        <img src={logoUrl} alt="" className="topbar-logo" />
        <div>
          <div className="topbar-eyebrow">OJIK BMS Client</div>
          <div className="topbar-title">{t("client.topbar.title")}</div>
        </div>
      </div>
      <div className="topbar-actions">
        <LanguageMenu value={language} onChange={onLanguageChange} />
        <Button
          variant="ghost"
          size="sm"
          leadingIcon={<ExternalLink size={15} aria-hidden="true" />}
          onClick={onOpenSite}
        >
          {t("client.topbar.openSite")}
        </Button>
        <AuthPill status={auth} />
        {auth?.logged_in ? (
          <Button
            variant="ghost"
            size="sm"
            leadingIcon={<LogOut size={15} aria-hidden="true" />}
            onClick={onLogout}
          >
            {t("client.topbar.logout")}
          </Button>
        ) : (
          <Button
            variant="primary"
            size="sm"
            leadingIcon={<LogIn size={15} aria-hidden="true" />}
            onClick={onLogin}
            disabled={isLoggingIn}
          >
            {isLoggingIn ? t("client.topbar.loggingIn") : t("client.topbar.login")}
          </Button>
        )}
        <Button
          variant="ghost"
          iconOnly
          aria-label={t("client.topbar.openDiagnostics")}
          onClick={onOpenDiagnostics}
        >
          <Info size={16} aria-hidden="true" />
        </Button>
      </div>
    </header>
  );
}
