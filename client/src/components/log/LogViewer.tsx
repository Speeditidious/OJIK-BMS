import { Bug, Copy, Eraser, FileText, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { formatLogTime, tokenizeMessage } from "../../lib/log-format";
import type { LogEntry, LogLevel } from "../../types";
import { Button } from "../primitives/Button";
import { Tabs, type TabItem } from "../primitives/Tabs";

type TabId = "all" | LogLevel;

export interface LogViewerProps {
  logs: LogEntry[];
  debugMode: boolean;
  onClear: () => void;
  onToggleDebugMode: () => void;
  onOpenLogFile?: () => void;
  onCopy?: (text: string) => void;
}

export function LogViewer({ logs, debugMode, onClear, onToggleDebugMode, onOpenLogFile, onCopy }: LogViewerProps) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<TabId>("all");
  const [query, setQuery] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  // When debug mode is turned off, switch away from the debug tab
  useEffect(() => {
    if (!debugMode && tab === "debug") setTab("all");
  }, [debugMode, tab]);

  const counts = useMemo(() => {
    const c = { info: 0, warn: 0, error: 0, debug: 0 };
    logs.forEach((l) => {
      if (l.level === "debug" && !debugMode) return;
      if (l.level in c) c[l.level as keyof typeof c] += 1;
    });
    return c;
  }, [logs, debugMode]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return logs.filter((entry) => {
      if (entry.level === "debug" && !debugMode) return false;
      if (tab !== "all" && entry.level !== tab) return false;
      if (q && !entry.message.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [logs, tab, query, debugMode]);

  // Auto-scroll to bottom when new logs arrive (unless user scrolled up).
  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    if (nearBottom) {
      el.scrollTop = el.scrollHeight;
    }
  }, [filtered]);

  const visibleLogCount = debugMode ? logs.length : logs.filter((l) => l.level !== "debug").length;
  const items: TabItem<TabId>[] = [
    { id: "all", label: t("client.logs.levels.all"), count: visibleLogCount },
    { id: "info", label: t("client.logs.levels.info"), count: counts.info },
    { id: "warn", label: t("client.logs.levels.warn"), count: counts.warn },
    { id: "error", label: t("client.logs.levels.error"), count: counts.error },
    ...(debugMode ? [{ id: "debug" as TabId, label: t("client.logs.levels.debug"), count: counts.debug }] : []),
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
    <section className="card" aria-label={t("client.logs.ariaLabel")}>
      <header className="card-hd">
        <div className="card-title">{t("client.logs.title")}</div>
      </header>
      <div className="card-bd log-viewer">
        <div className="log-controls">
          <Tabs items={items} value={tab} onChange={setTab} ariaLabel={t("client.logs.filterAria")} />
          <div className="log-search">
            <Search size={14} aria-hidden="true" className="log-search-icon" />
            <input
              type="search"
              placeholder={t("client.logs.searchPlaceholder")}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label={t("client.logs.searchAria")}
            />
          </div>
          <div className="log-actions">
            <Button
              variant="ghost"
              size="sm"
              leadingIcon={<Bug size={14} />}
              onClick={onToggleDebugMode}
              aria-pressed={debugMode}
              className={debugMode ? "log-debug-toggle-active" : undefined}
              title={debugMode ? t("client.logs.debugOff") : t("client.logs.debugOn")}
            >
              {t("client.logs.debugLabel")}
            </Button>
            <Button variant="ghost" size="sm" leadingIcon={<Copy size={14} />} onClick={handleCopy} disabled={filtered.length === 0}>
              {t("client.logs.copy")}
            </Button>
            {onOpenLogFile ? (
              <Button variant="ghost" size="sm" leadingIcon={<FileText size={14} />} onClick={onOpenLogFile}>
                {t("client.logs.file")}
              </Button>
            ) : null}
            <Button variant="ghost" size="sm" leadingIcon={<Eraser size={14} />} onClick={onClear} disabled={logs.length === 0}>
              {t("client.logs.clear")}
            </Button>
          </div>
        </div>

        <div className="log-list" ref={listRef} role="log" aria-live="polite">
          {filtered.length === 0 ? (
            <div className="log-empty">
              {logs.length === 0
                ? t("client.logs.emptyBeforeSync")
                : t("client.logs.emptyFiltered")}
            </div>
          ) : (
            filtered.map((entry) => <LogRow key={entry.id} entry={entry} />)
          )}
        </div>
      </div>
    </section>
  );
}

function LogRow({ entry }: { entry: LogEntry }) {
  const { t } = useTranslation();
  const tokens = useMemo(() => tokenizeMessage(entry.message), [entry.message]);

  const levelKey = `client.logs.levels.${entry.level}` as const;
  const levelLabel = t(levelKey, { defaultValue: entry.level });

  return (
    <div className="log-row">
      <span className="log-time">{formatLogTime(entry.ts)}</span>
      <span className={`log-level log-level-${entry.level}`}>{levelLabel}</span>
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
