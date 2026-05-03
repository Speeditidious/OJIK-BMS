import { AlertTriangle, Download, RefreshCw } from "lucide-react";

import type { UpdateError } from "../../types";
import { Button } from "../primitives/Button";
import { Dialog } from "../primitives/Dialog";

const STAGE_LABEL: Record<UpdateError["stage"], string> = {
  check: "업데이트 확인",
  download: "업데이트 다운로드",
  verify: "서명 검증",
  install: "설치",
  restart: "재시작",
};

export function UpdateFailureDialog({
  open,
  error,
  mandatory,
  onRetry,
  onOpenDownloadPage,
  onClose,
}: {
  open: boolean;
  error: UpdateError;
  mandatory: boolean;
  onRetry: () => void;
  onOpenDownloadPage: () => void;
  onClose: () => void;
}) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      dismissable={!mandatory}
      title={
        <span style={{ color: "var(--danger)", display: "inline-flex", alignItems: "center", gap: 6 }}>
          <AlertTriangle size={16} aria-hidden="true" />
          업데이트가 실패했습니다
        </span>
      }
      footer={
        <>
          {!mandatory ? (
            <Button variant="ghost" onClick={onClose}>
              닫기
            </Button>
          ) : null}
          <Button
            variant="default"
            leadingIcon={<Download size={14} aria-hidden="true" />}
            onClick={onOpenDownloadPage}
          >
            다운로드 페이지 열기
          </Button>
          <Button
            variant="primary"
            leadingIcon={<RefreshCw size={14} aria-hidden="true" />}
            onClick={onRetry}
          >
            다시 시도
          </Button>
        </>
      }
    >
      <div style={{ display: "grid", gap: 10 }}>
        <div style={{ color: "var(--muted)", fontSize: "0.86rem" }}>
          단계: <b style={{ color: "var(--text)" }}>{STAGE_LABEL[error.stage]}</b>
        </div>
        <pre
          style={{
            color: "var(--danger)",
            background: "var(--surface-2)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: 12,
            fontSize: "0.84rem",
            maxHeight: 200,
            overflowY: "auto",
            margin: 0,
            whiteSpace: "pre-wrap",
          }}
        >
          {error.message}
        </pre>
        {mandatory ? (
          <div className="banner banner-warn">
            <div>
              <div className="banner-title">필수 업데이트가 끝나야 동기화가 다시 활성화됩니다</div>
              <div className="banner-body">
                다시 시도가 계속 실패하면 다운로드 페이지에서 수동으로 최신 인스톨러를 받아 주세요.
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </Dialog>
  );
}
