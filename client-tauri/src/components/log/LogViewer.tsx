import { Copy, Eraser, FileText, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { formatLogTime, tokenizeMessage } from "../../lib/log-format";
import type { LogEntry, LogLevel } from "../../types";
import { Button } from "../primitives/Button";
import { Tabs, type TabItem } from "../primitives/Tabs";

type TabId = "all" | LogLevel;

export interface LogViewerProps {
  logs: LogEntry[];
  overflowed: boolean;
  onClear: () => void;
  onOpenLogFile?: () => void;
  onCopy?: (text: string) => void;
}

export function LogViewer({ logs, overflowed, onClear, onOpenLogFile, onCopy }: LogViewerProps) {
  const [tab, setTab] = useState<TabId>("all");
  const [query, setQuery] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  const counts = useMemo(() => {
    const c = { info: 0, warn: 0, error: 0 };
    logs.forEach((l) => {
      c[l.level] += 1;
    });
    return c;
  }, [logs]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return logs.filter((entry) => {
      if (tab !== "all" && entry.level !== tab) return false;
      if (q && !entry.message.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [logs, tab, query]);

  // Auto-scroll to bottom when new logs arrive (unless user scrolled up).
  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    if (nearBottom) {
      el.scrollTop = el.scrollHeight;
    }
  }, [filtered]);

  const items: TabItem<TabId>[] = [
    { id: "all", label: "전체", count: logs.length },
    { id: "info", label: "정보", count: counts.info },
    { id: "warn", label: "경고", count: counts.warn },
    { id: "error", label: "오류", count: counts.error },
  ];

  function handleCopy() {
    const text = filtered
      .map((l) => `[${formatLogTime(l.ts)}] ${l.level.toUpperCase()} ${l.message}`)
      .join("\n");
    if (onCopy) {
      onCopy(text);
    } else {
      navigator.clipboard?.writeText(text).catch(() => {});
    }
  }

  return (
    <section className="card" aria-label="활동 로그">
      <header className="card-hd">
        <div className="card-title">활동 로그</div>
      </header>
      <div className="card-bd log-viewer">
        <div className="log-controls">
          <Tabs items={items} value={tab} onChange={setTab} ariaLabel="로그 레벨 필터" />
          <div className="log-search">
            <Search size={14} aria-hidden="true" className="log-search-icon" />
            <input
              type="search"
              placeholder="로그 검색"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="로그 검색"
            />
          </div>
          <div className="log-actions">
            <Button variant="ghost" size="sm" leadingIcon={<Copy size={14} />} onClick={handleCopy} disabled={filtered.length === 0}>
              복사
            </Button>
            {onOpenLogFile ? (
              <Button variant="ghost" size="sm" leadingIcon={<FileText size={14} />} onClick={onOpenLogFile}>
                파일
              </Button>
            ) : null}
            <Button variant="ghost" size="sm" leadingIcon={<Eraser size={14} />} onClick={onClear} disabled={logs.length === 0}>
              지우기
            </Button>
          </div>
        </div>

        <div className="log-list" ref={listRef} role="log" aria-live="polite">
          {filtered.length === 0 ? (
            <div className="log-empty">
              {logs.length === 0
                ? "동기화를 시작하면 진행 상황이 여기에 표시됩니다."
                : "필터에 일치하는 로그가 없습니다."}
            </div>
          ) : (
            filtered.map((entry) => <LogRow key={entry.id} entry={entry} />)
          )}
        </div>

        {overflowed ? (
          <p className="log-overflow-note">
            메모리에는 최근 1,000줄만 보관합니다. 전체 로그는 “파일” 버튼으로 확인하세요.
          </p>
        ) : null}
      </div>
    </section>
  );
}

function LogRow({ entry }: { entry: LogEntry }) {
  const tokens = useMemo(() => tokenizeMessage(entry.message), [entry.message]);
  return (
    <div className="log-row">
      <span className="log-time">{formatLogTime(entry.ts)}</span>
      <span className={`log-level log-level-${entry.level}`}>{entry.level}</span>
      <span className="log-msg">
        {tokens.map((tok, idx) =>
          tok.type === "link" && tok.href ? (
            <a key={idx} href={tok.href} target="_blank" rel="noreferrer noopener">
              {tok.value}
            </a>
          ) : (
            <span key={idx}>{tok.value}</span>
          ),
        )}
      </span>
    </div>
  );
}
