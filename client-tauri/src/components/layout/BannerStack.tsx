import { AlertTriangle, ShieldAlert, Download } from "lucide-react";

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
  if (syncRunning) return null;

  const banners: React.ReactNode[] = [];

  if (policy?.update_available && policy.announcement?.mandatory) {
    banners.push(
      <div className="banner banner-danger" key="mandatory">
        <ShieldAlert size={18} aria-hidden="true" />
        <div>
          <div className="banner-title">필수 업데이트가 필요합니다 — {policy.announcement.version}</div>
          <div className="banner-body">{policy.announcement.title}</div>
        </div>
        <div className="banner-actions">
          <Button variant="primary" size="sm" onClick={onInstallUpdate}>
            지금 업데이트
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
              ? "로그인 세션이 만료되었어요"
              : "동기화하려면 Discord 로그인이 필요합니다"}
          </div>
          <div className="banner-body">
            {isExpired
              ? "다시 로그인하면 동기화를 이어서 진행할 수 있어요."
              : "로그인 후 경로를 선택해 첫 동기화를 시작하세요."}
          </div>
        </div>
        <div className="banner-actions">
          <Button variant="primary" size="sm" onClick={onLogin}>
            {isExpired ? "다시 로그인" : "지금 로그인"}
          </Button>
        </div>
      </div>,
    );
  } else if (auth?.logged_in && typeof days === "number" && days <= 3) {
    banners.push(
      <div className="banner banner-warn" key="expiring">
        <AlertTriangle size={18} aria-hidden="true" />
        <div>
          <div className="banner-title">로그인 세션이 곧 만료됩니다 (D-{Math.max(0, days)})</div>
          <div className="banner-body">미리 재로그인해 두면 다음 동기화가 끊기지 않습니다.</div>
        </div>
        <div className="banner-actions">
          <Button variant="primary" size="sm" onClick={onLogin}>
            재로그인
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
            이전 업데이트가 실패했습니다
            {config.last_update_failure_version ? ` (${config.last_update_failure_version})` : ""}
          </div>
          <div className="banner-body">{config.last_update_failure_message}</div>
        </div>
        <div className="banner-actions">
          <Button variant="default" size="sm" onClick={onOpenDownloadPage}>
            다운로드 페이지 열기
          </Button>
          <Button variant="ghost" size="sm" onClick={onClearUpdateFailure}>
            닫기
          </Button>
        </div>
      </div>,
    );
  }

  if (banners.length === 0) return null;
  return <div className="banner-stack">{banners}</div>;
}
