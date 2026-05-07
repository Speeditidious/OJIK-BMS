import { ExternalLink, Info, LogIn, LogOut } from "lucide-react";

import logoUrl from "../../assets/ojikbms_logo.png";
import type { AuthStatus } from "../../types";
import { AuthPill } from "../auth/AuthPill";
import { Button } from "../primitives/Button";

export function Topbar({
  auth,
  onLogin,
  onLogout,
  onOpenDiagnostics,
  onOpenSite,
  isLoggingIn,
}: {
  auth: AuthStatus | null;
  onLogin: () => void;
  onLogout: () => void;
  onOpenDiagnostics: () => void;
  onOpenSite: () => void;
  isLoggingIn: boolean;
}) {
  return (
    <header className="topbar">
      <div className="topbar-brand">
        <img src={logoUrl} alt="" className="topbar-logo" />
        <div>
          <div className="topbar-eyebrow">OJIK BMS Client</div>
          <div className="topbar-title">동기화 대시보드</div>
        </div>
      </div>
      <div className="topbar-actions">
        <Button
          variant="ghost"
          size="sm"
          leadingIcon={<ExternalLink size={15} aria-hidden="true" />}
          onClick={onOpenSite}
        >
          사이트 바로가기
        </Button>
        <AuthPill status={auth} />
        {auth?.logged_in ? (
          <Button
            variant="ghost"
            size="sm"
            leadingIcon={<LogOut size={15} aria-hidden="true" />}
            onClick={onLogout}
          >
            로그아웃
          </Button>
        ) : (
          <Button
            variant="primary"
            size="sm"
            leadingIcon={<LogIn size={15} aria-hidden="true" />}
            onClick={onLogin}
            disabled={isLoggingIn}
          >
            {isLoggingIn ? "로그인 중…" : "Discord 로그인"}
          </Button>
        )}
        <Button
          variant="ghost"
          iconOnly
          aria-label="정보 열기"
          onClick={onOpenDiagnostics}
        >
          <Info size={16} aria-hidden="true" />
        </Button>
      </div>
    </header>
  );
}
