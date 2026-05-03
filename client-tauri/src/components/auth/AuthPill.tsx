import { CircleUserRound, ShieldCheck, ShieldAlert } from "lucide-react";
import type { AuthStatus } from "../../types";

export function AuthPill({ status }: { status: AuthStatus | null }) {
  if (!status) {
    return (
      <span className="authpill authpill-out">
        <CircleUserRound size={14} aria-hidden="true" />
        확인 중
      </span>
    );
  }

  if (!status.logged_in) {
    return (
      <span className="authpill authpill-out" title="Discord 로그인이 필요합니다">
        <CircleUserRound size={14} aria-hidden="true" />
        로그인 필요
      </span>
    );
  }

  const expiringSoon =
    typeof status.refresh_token_expire_days === "number" && status.refresh_token_expire_days <= 3;

  return (
    <span
      className={expiringSoon ? "authpill authpill-warn" : "authpill authpill-ok"}
      title={expiringSoon ? "로그인 세션이 곧 만료됩니다" : undefined}
    >
      {expiringSoon ? <ShieldAlert size={14} aria-hidden="true" /> : <ShieldCheck size={14} aria-hidden="true" />}
      로그인됨
    </span>
  );
}
