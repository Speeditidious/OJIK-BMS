import { Download, ExternalLink, FileText } from "lucide-react";

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
  return (
    <footer className="about-footer">
      <div className="about-meta">
        <span>
          <b>버전</b> v{version}
        </span>
        <span>
          <b>채널</b> {channel}
        </span>
        <span>
          <b>웹</b> ojikbms.kr
        </span>
      </div>
      <div className="about-actions">
        {onOpenLogFile ? (
          <Button variant="ghost" size="sm" leadingIcon={<FileText size={14} aria-hidden="true" />} onClick={onOpenLogFile}>
            로그 파일
          </Button>
        ) : null}
        <Button
          variant="ghost"
          size="sm"
          leadingIcon={<ExternalLink size={14} aria-hidden="true" />}
          onClick={onOpenSite}
        >
          사이트 바로가기
        </Button>
        <Button
          variant="ghost"
          size="sm"
          leadingIcon={<Download size={14} aria-hidden="true" />}
          onClick={onOpenDownloadPage}
        >
          다운로드 페이지
        </Button>
      </div>
    </footer>
  );
}
