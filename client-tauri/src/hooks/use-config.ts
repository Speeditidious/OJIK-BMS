import { useCallback, useEffect, useRef, useState } from "react";

import { getConfig, importLegacyConfig, saveConfig } from "../tauri";
import type { ClientConfig } from "../types";

export type LoadState = "loading" | "ready" | "error";
export type SaveState = "idle" | "saving" | "saved" | "error";

export function useConfigStore() {
  const [config, setConfig] = useState<ClientConfig | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [error, setError] = useState<string | null>(null);
  const initialLoadDone = useRef(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const next = await getConfig();
        if (cancelled) return;
        setConfig(next);
        setLoadState("ready");
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
        setLoadState("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Debounced auto-save when config changes after initial load.
  useEffect(() => {
    if (loadState !== "ready" || !config) return;
    if (!initialLoadDone.current) {
      initialLoadDone.current = true;
      return;
    }
    setSaveState("saving");
    const timer = window.setTimeout(async () => {
      try {
        const next = await saveConfig(config);
        if (JSON.stringify(next) !== JSON.stringify(config)) {
          setConfig(next);
        }
        setSaveState("saved");
        window.setTimeout(() => setSaveState("idle"), 1200);
      } catch (err) {
        setSaveState("error");
        setError(err instanceof Error ? err.message : String(err));
      }
    }, 400);
    return () => window.clearTimeout(timer);
  }, [config, loadState]);

  const update = useCallback(<K extends keyof ClientConfig>(patch: Partial<ClientConfig> | ((prev: ClientConfig) => Partial<ClientConfig>)) => {
    setConfig((prev) => {
      if (!prev) return prev;
      const next = typeof patch === "function" ? patch(prev) : patch;
      return { ...prev, ...next } as ClientConfig;
    });
    // K is unused but kept for type-safety on future field-level setters.
    void (undefined as unknown as K);
  }, []);

  const importLegacy = useCallback(async (path: string) => {
    const next = await importLegacyConfig(path);
    setConfig(next);
    return next;
  }, []);

  return { config, loadState, saveState, error, update, importLegacy };
}
