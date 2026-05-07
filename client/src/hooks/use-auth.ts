import { useCallback, useEffect, useState } from "react";

import { subscribe } from "../lib/tauri-events";
import { getAuthStatus, logout as logoutCmd, startLogin } from "../tauri";
import type { AuthStatus } from "../types";

export function useAuthStore() {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getAuthStatus()
      .then((next) => {
        if (!cancelled) setStatus(next);
      })
      .catch(() => {
        if (!cancelled) setStatus({ logged_in: false, refresh_token_expire_days: null });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let unlisten: (() => void) | null = null;
    let active = true;
    subscribe<AuthStatus>("auth:changed", (payload) => {
      setStatus(payload);
    }).then((fn) => {
      if (active) {
        unlisten = fn;
      } else {
        fn();
      }
    });
    return () => {
      active = false;
      unlisten?.();
    };
  }, []);

  const login = useCallback(async () => {
    setIsLoggingIn(true);
    try {
      const next = await startLogin();
      setStatus(next);
      return next;
    } finally {
      setIsLoggingIn(false);
    }
  }, []);

  const logout = useCallback(async () => {
    const next = await logoutCmd();
    setStatus(next);
    return next;
  }, []);

  return { status, isLoggingIn, login, logout };
}
