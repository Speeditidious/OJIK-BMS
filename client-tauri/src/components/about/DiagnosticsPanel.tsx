import { Download, FileText, RefreshCw, RotateCcw } from "lucide-react";

import type { ClientConfig } from "../../types";
import { Button } from "../primitives/Button";
import { Dialog } from "../primitives/Dialog";

export interface DiagnosticsInfo {
  version: string;
  channel: string;
  os?: string | null;
  webview?: string | null;
  apiUrl: string;
  configDir?: string | null;
  logsDir?: string | null;
}

export function DiagnosticsPanel({
  open,
  onClose,
  info,
  config,
  onCheckUpdate,
  onOpenDownloadPage,
  onOpenLogFile,
  onResetUpdateDismissals,
  isCheckingUpdate,
}: {
  open: boolean;
  onClose: () => void;
  info: DiagnosticsInfo;
  config: ClientConfig | null;
  onCheckUpdate: () => void;
  onOpenDownloadPage: () => void;
  onOpenLogFile?: () => void;
  onResetUpdateDismissals: () => void;
  isCheckingUpdate: boolean;
}) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="정보"
      footer={
        <Button variant="ghost" onClick={onClose}>
          닫기
        </Button>
      }
    >
      <div style={{ display: "grid", gap: 14 }}>
        <DiagSection title="앱 정보">
          <DiagRow label="버전" value={`v${info.version}`} />
          <DiagRow label="채널" value={info.channel} />
          {info.os ? <DiagRow label="OS" value={info.os} /> : null}
          {info.webview ? <DiagRow label="WebView2" value={info.webview} /> : null}
          <DiagRow label="API URL" value={info.apiUrl} />
          {info.configDir ? <DiagRow label="Config 경로" value={info.configDir} mono /> : null}
          {info.logsDir ? <DiagRow label="Logs 경로" value={info.logsDir} mono /> : null}
        </DiagSection>

        <DiagSection title="업데이트">
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Button
              size="sm"
              leadingIcon={
                <RefreshCw size={14} aria-hidden="true" className={isCheckingUpdate ? "spin" : undefined} />
              }
              onClick={onCheckUpdate}
              disabled={isCheckingUpdate}
            >
              지금 확인
            </Button>
            <Button
              size="sm"
              variant="ghost"
              leadingIcon={<Download size={14} aria-hidden="true" />}
              onClick={onOpenDownloadPage}
            >
              다운로드 페이지
            </Button>
            <Button
              size="sm"
              variant="ghost"
              leadingIcon={<RotateCcw size={14} aria-hidden="true" />}
              onClick={onResetUpdateDismissals}
              disabled={!config?.dismissed_update_id && !config?.dismissed_update_until && !config?.skipped_update_version}
            >
              숨긴 업데이트 알림 다시 보기
            </Button>
          </div>
          {config?.skipped_update_version ? (
            <div style={{ color: "var(--muted)", fontSize: "0.82rem" }}>
              건너뛴 버전: {config.skipped_update_version}
            </div>
          ) : null}
        </DiagSection>

        {onOpenLogFile ? (
          <DiagSection title="로그">
            <Button
              size="sm"
              variant="ghost"
              leadingIcon={<FileText size={14} aria-hidden="true" />}
              onClick={onOpenLogFile}
            >
              로그 파일 열기
            </Button>
          </DiagSection>
        ) : null}
      </div>
    </Dialog>
  );
}

function DiagSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ display: "grid", gap: 8 }}>
      <h3 style={{ fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--primary)" }}>
        {title}
      </h3>
      <div style={{ display: "grid", gap: 6 }}>{children}</div>
    </section>
  );
}

function DiagRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 8, fontSize: "0.86rem" }}>
      <span style={{ color: "var(--muted)" }}>{label}</span>
      <span
        style={{
          color: "var(--text)",
          wordBreak: "break-all",
          fontFamily: mono ? '"Consolas", "D2Coding", monospace' : undefined,
        }}
      >
        {value}
      </span>
    </div>
  );
}
