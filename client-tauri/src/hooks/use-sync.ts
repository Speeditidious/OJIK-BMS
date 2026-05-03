import { useCallback, useEffect, useRef, useState } from "react";

import { fromEvent, makeEntry } from "../lib/log-format";
import { formatNumber } from "../lib/format";
import { subscribe } from "../lib/tauri-events";
import { cancelSync, startSync } from "../tauri";
import type {
  LogEntry,
  LogEvent,
  SyncProgressEvent,
  SyncRequest,
  SyncResult,
  SyncStage,
} from "../types";

export type SyncState = "idle" | "running" | "finished" | "error" | "cancelled";

const LOG_CAP = 1000;

interface ProgressMap {
  global?: SyncProgressEvent;
  lr2?: SyncProgressEvent;
  beatoraja?: SyncProgressEvent;
}

export function useSyncStore() {
  const [state, setState] = useState<SyncState>("idle");
  const [progress, setProgress] = useState<ProgressMap>({});
  const [stage, setStage] = useState<SyncStage | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [overflowed, setOverflowed] = useState(false);
  const [lastResult, setLastResult] = useState<SyncResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const currentRunId = useRef<string | null>(null);

  const pushLog = useCallback((entry: LogEntry) => {
    setLogs((prev) => {
      const next = [...prev, entry];
      if (next.length > LOG_CAP) {
        setOverflowed(true);
        return next.slice(next.length - LOG_CAP);
      }
      return next;
    });
  }, []);

  const clearLogs = useCallback(() => {
    setLogs([]);
    setOverflowed(false);
  }, []);

  useEffect(() => {
    const unlisteners: Array<() => void> = [];
    let active = true;
    const collect = (promise: Promise<() => void>) => {
      promise.then((fn) => {
        if (active) {
          unlisteners.push(fn);
        } else {
          fn();
        }
      });
    };

    collect(subscribe<{ sync_run_id: string; client_filter: string; full_sync: boolean }>(
      "sync:started",
      (payload) => {
        currentRunId.current = payload.sync_run_id;
        setState("running");
        setProgress({});
        setStage("validating");
        setErrorMessage(null);
        pushLog(
          makeEntry({
            level: "info",
            message: `동기화를 시작합니다 (${payload.client_filter}${payload.full_sync ? ", 전체" : ""}).`,
          }),
        );
      },
    ));

    collect(subscribe<SyncProgressEvent>("sync:progress", (payload) => {
      setStage(payload.stage);
      setProgress((prev) => {
        const next = { ...prev };
        if (!payload.client) {
          next.global = payload;
        } else {
          next[payload.client] = payload;
        }
        return next;
      });
    }));

    collect(subscribe<LogEvent>("sync:log", (payload) => {
      pushLog(fromEvent(payload));
    }));

    collect(subscribe<SyncResult>("sync:finished", (payload) => {
      setLastResult(payload);
      setState("finished");
      setStage("done");
      pushLog(
        makeEntry({
          level: "info",
          message: `동기화 완료 — 등록된 기록 ${formatNumber(payload.inserted)}건, 수정된 기록 ${formatNumber(payload.metadata_updated)}건`,
        }),
      );
    }));

    collect(subscribe<{ message: string }>("sync:error", (payload) => {
      setErrorMessage(payload.message);
      setState("error");
      pushLog(makeEntry({ level: "error", message: payload.message }));
    }));

    collect(subscribe<{ sync_run_id: string }>("sync:cancelled", () => {
      setState("cancelled");
      pushLog(makeEntry({ level: "warn", message: "동기화가 취소되었습니다." }));
    }));

    return () => {
      active = false;
      unlisteners.forEach((fn) => fn());
    };
  }, [pushLog]);

  const start = useCallback(
    async (request: SyncRequest) => {
      try {
        const handle = await startSync(request);
        currentRunId.current = handle.id;
        return handle;
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setErrorMessage(msg);
        setState("error");
        pushLog(makeEntry({ level: "error", message: msg }));
        throw err;
      }
    },
    [pushLog],
  );

  const cancel = useCallback(async () => {
    if (!currentRunId.current) return;
    try {
      await cancelSync(currentRunId.current);
    } catch (err) {
      pushLog(
        makeEntry({
          level: "error",
          message: `취소 요청 실패: ${err instanceof Error ? err.message : String(err)}`,
        }),
      );
    }
  }, [pushLog]);

  return {
    state,
    stage,
    progress,
    logs,
    overflowed,
    lastResult,
    errorMessage,
    start,
    cancel,
    clearLogs,
    pushLog,
  };
}
