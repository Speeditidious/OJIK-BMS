import { useCallback, useEffect, useState } from "react";

import { subscribe } from "../lib/tauri-events";
import { checkUpdatePolicy, installUpdate, openDownloadPage } from "../tauri";
import type { UpdateAnnouncement, UpdateError, UpdatePolicy } from "../types";

const UPDATE_CHECK_INTERVAL_MS = 5 * 60 * 1000;

export function useUpdateStore() {
  const [policy, setPolicy] = useState<UpdatePolicy | null>(null);
  const [downloadProgress, setDownloadProgress] = useState<{ downloaded: number; total?: number | null } | null>(null);
  const [installError, setInstallError] = useState<UpdateError | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [isInstalling, setIsInstalling] = useState(false);

  // Background check on mount.
  useEffect(() => {
    let cancelled = false;
    const check = () => {
      checkUpdatePolicy(false)
        .then((next) => {
          if (!cancelled) setPolicy(next);
        })
        .catch(() => {});
    };
    check();
    const timer = window.setInterval(check, UPDATE_CHECK_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
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

    collect(subscribe<UpdateAnnouncement>("update:available", (payload) => {
      setPolicy({ update_available: true, message: null, announcement: payload });
    }));

    collect(subscribe<{ downloaded: number; total?: number | null }>("update:download-progress", (payload) => {
      setDownloadProgress(payload);
    }));

    collect(subscribe<UpdateError>("update:error", (payload) => {
      setInstallError(payload);
      setIsInstalling(false);
    }));

    return () => {
      active = false;
      unlisteners.forEach((fn) => fn());
    };
  }, []);

  const manualCheck = useCallback(async () => {
    setIsChecking(true);
    try {
      const next = await checkUpdatePolicy(true);
      setPolicy(next);
      return next;
    } finally {
      setIsChecking(false);
    }
  }, []);

  const install = useCallback(async (id: string) => {
    setInstallError(null);
    setIsInstalling(true);
    try {
      await installUpdate(id);
    } catch (err) {
      setInstallError({
        stage: "install",
        message: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setIsInstalling(false);
    }
  }, []);

  const openDownload = useCallback(async () => {
    return openDownloadPage();
  }, []);

  return {
    policy,
    downloadProgress,
    installError,
    isChecking,
    isInstalling,
    manualCheck,
    install,
    openDownload,
  };
}
