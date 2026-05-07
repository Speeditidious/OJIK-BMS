import type { LogEntry, LogEvent, LogLevel } from "../types";

let logCounter = 0;

export function nextLogId(): string {
  logCounter += 1;
  return `log-${Date.now()}-${logCounter}`;
}

export function makeEntry(input: { level?: LogLevel; message: string; ts?: string | null }): LogEntry {
  return {
    id: nextLogId(),
    level: input.level ?? "info",
    message: input.message,
    ts: input.ts ?? new Date().toISOString(),
  };
}

export function fromEvent(event: LogEvent): LogEntry {
  return makeEntry({ level: event.level, message: event.message, ts: event.ts });
}

export function formatLogTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

const URL_PATTERN = /(https?:\/\/[^\s)]+)/g;

export interface LogToken {
  type: "text" | "link";
  value: string;
  href?: string;
}

export function tokenizeMessage(message: string): LogToken[] {
  const tokens: LogToken[] = [];
  let lastIndex = 0;
  for (const match of message.matchAll(URL_PATTERN)) {
    const start = match.index ?? 0;
    if (start > lastIndex) {
      tokens.push({ type: "text", value: message.slice(lastIndex, start) });
    }
    tokens.push({ type: "link", value: match[0], href: match[0] });
    lastIndex = start + match[0].length;
  }
  if (lastIndex < message.length) {
    tokens.push({ type: "text", value: message.slice(lastIndex) });
  }
  if (tokens.length === 0) tokens.push({ type: "text", value: message });
  return tokens;
}
