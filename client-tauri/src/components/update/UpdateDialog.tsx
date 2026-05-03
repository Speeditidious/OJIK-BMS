import { Download, ExternalLink } from "lucide-react";

import { formatBytes } from "../../lib/format";
import type { UpdateAnnouncement } from "../../types";
import { Button } from "../primitives/Button";
import { Dialog } from "../primitives/Dialog";

export interface UpdateDialogProps {
  open: boolean;
  announcement: UpdateAnnouncement;
  isInstalling: boolean;
  downloadProgress?: { downloaded: number; total?: number | null } | null;
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
  onInstall,
  onLater,
  onSkip,
  onOpenReleasePage,
  onClose,
}: UpdateDialogProps) {
  const mandatory = announcement.mandatory;
  const dismissable = !mandatory;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      dismissable={dismissable}
      closeOnBackdrop={dismissable}
      title={
        <span>
          {mandatory ? "필수 업데이트" : "새 버전이 준비되어 있어요"} ·{" "}
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
              릴리즈 페이지
            </Button>
          ) : null}
          {!mandatory ? (
            <>
              {onSkip ? (
                <Button variant="ghost" onClick={onSkip}>
                  이 버전 건너뛰기
                </Button>
              ) : null}
              {onLater ? (
                <Button variant="default" onClick={onLater}>
                  나중에
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
            {isInstalling ? "설치 진행 중…" : "지금 업데이트"}
          </Button>
        </>
      }
    >
      <div style={{ display: "grid", gap: 12 }}>
        <h2 style={{ fontSize: "1.05rem" }}>{announcement.title}</h2>

        <div style={{ display: "flex", gap: 14, color: "var(--muted)", fontSize: "0.84rem", flexWrap: "wrap" }}>
          {announcement.asset_size_bytes ? (
            <span>다운로드 크기: <b style={{ color: "var(--text)" }}>{formatBytes(announcement.asset_size_bytes)}</b></span>
          ) : null}
          {announcement.published_at ? (
            <span>배포일: <b style={{ color: "var(--text)" }}>{new Date(announcement.published_at).toLocaleDateString()}</b></span>
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
          {announcement.body_markdown}
        </pre>

        {downloadProgress ? (
          <DownloadProgress downloaded={downloadProgress.downloaded} total={downloadProgress.total ?? null} />
        ) : null}

        {mandatory ? (
          <div className="banner banner-warn">
            <div>
              <div className="banner-title">이번 업데이트는 필수입니다</div>
              <div className="banner-body">
                동기화는 업데이트 완료 또는 수동 설치 전까지 일시적으로 비활성화됩니다.
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </Dialog>
  );
}

function DownloadProgress({ downloaded, total }: { downloaded: number; total: number | null }) {
  const indeterminate = !total || total <= 0;
  const pct = indeterminate ? 0 : Math.min(100, (downloaded / total) * 100);
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <div className={`sync-bar${indeterminate ? " is-indeterminate" : ""}`} style={{ height: 8 }}>
        <span className="sync-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span style={{ color: "var(--muted)", fontSize: "0.78rem" }}>
        {indeterminate ? "다운로드 중…" : `${formatBytes(downloaded)} / ${formatBytes(total)}`}
      </span>
    </div>
  );
}
