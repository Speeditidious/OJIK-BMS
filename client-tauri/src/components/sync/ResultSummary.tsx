import { ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";

import { formatNumber, formatRelativeTime } from "../../lib/format";
import type { SyncResult } from "../../types";
import { Button } from "../primitives/Button";

export interface ResultSummaryProps {
  result: SyncResult | null;
  onOpenResultUrl?: (url: string) => void;
  onJumpToLog?: () => void;
}

export function ResultSummary({ result, onOpenResultUrl, onJumpToLog }: ResultSummaryProps) {
  const [open, setOpen] = useState(false);

  // Auto-expand once when a fresh result arrives.
  useEffect(() => {
    if (result) setOpen(true);
  }, [result]);

  if (!result) return null;

  const errorCount = result.errors.length;
  const resultUrl = result.result_url ?? "https://www.ojikbms.kr/dashboard";

  return (
    <section className="card fade-in" aria-label="동기화 결과">
      <header className="card-hd">
        <div className="card-title">
          최근 동기화 결과
          <span style={{ color: "var(--muted)", fontWeight: 400, marginLeft: 8 }}>
            {formatRelativeTime(result.finished_at)}
          </span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          leadingIcon={open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "접기" : "펼치기"}
        </Button>
      </header>

      {open ? (
        <div className="card-bd">
          <div className="result-stats">
            <div className="result-stat result-stat-new">
              <span className="result-stat-label">등록된 기록</span>
              <span className="result-stat-value">
                <b>{formatNumber(result.inserted)}</b>
              </span>
            </div>
            <div className="result-stat result-stat-improved">
              <span className="result-stat-label">수정된 기록</span>
              <span className="result-stat-value">
                <b>{formatNumber(result.metadata_updated)}</b>
              </span>
            </div>
            <div className="result-stat result-stat-error">
              <span className="result-stat-label">오류</span>
              <span className="result-stat-value">
                <b>{formatNumber(errorCount)}</b>
              </span>
            </div>
          </div>

          {errorCount > 0 ? (
            <div className="result-extra">
              <strong style={{ color: "var(--danger)" }}>오류 {formatNumber(errorCount)}건</strong>
              <ul>
                {result.errors.slice(0, 5).map((err, idx) => (
                  <li key={idx}>
                    {err.client ? `[${err.client}] ` : ""}
                    {err.message}
                  </li>
                ))}
                {errorCount > 5 ? (
                  <li>
                    외 {errorCount - 5}건 더 있음 —{" "}
                    <button type="button" className="btn btn-ghost btn-sm" onClick={onJumpToLog}>
                      로그에서 보기
                    </button>
                  </li>
                ) : null}
              </ul>
            </div>
          ) : null}

          <div className="result-cta">
            <span style={{ color: "var(--muted)", fontSize: "0.84rem" }}>
              사이트에서 동기화된 플레이 데이터를 확인할 수 있습니다.
            </span>
            <Button
              variant="primary"
              leadingIcon={<ExternalLink size={14} aria-hidden="true" />}
              onClick={() => onOpenResultUrl?.(resultUrl)}
            >
              사이트에서 결과 확인
            </Button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
