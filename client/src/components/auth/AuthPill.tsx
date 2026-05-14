import { CircleUserRound, ShieldCheck, ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { AuthStatus } from "../../types";

export function AuthPill({ status }: { status: AuthStatus | null }) {
  const { t } = useTranslation();

  if (!status) {
    return (
      <span className="authpill authpill-out">
        <CircleUserRound size={14} aria-hidden="true" />
        {t("client.authPill.checking")}
      </span>
    );
  }

  if (!status.logged_in) {
    return (
      <span className="authpill authpill-out" title={t("client.authPill.loginRequiredTitle")}>
        <CircleUserRound size={14} aria-hidden="true" />
        {t("client.authPill.loginRequired")}
      </span>
    );
  }

  const expiringSoon =
    typeof status.refresh_token_expire_days === "number" && status.refresh_token_expire_days <= 3;

  return (
    <span
      className={expiringSoon ? "authpill authpill-warn" : "authpill authpill-ok"}
      title={expiringSoon ? t("client.authPill.expiringSoonTitle") : undefined}
    >
      {expiringSoon ? <ShieldAlert size={14} aria-hidden="true" /> : <ShieldCheck size={14} aria-hidden="true" />}
      {t("client.authPill.loggedIn")}
    </span>
  );
}
