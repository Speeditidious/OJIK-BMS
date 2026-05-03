import { useCallback, useState } from "react";

export type ToastTone = "info" | "success" | "warn" | "error";

export interface Toast {
  id: string;
  tone?: ToastTone;
  title?: string;
  message: string;
  durationMs?: number;
  persistent?: boolean;
}

export interface ToastInput {
  tone?: ToastTone;
  title?: string;
  message: string;
  durationMs?: number;
  persistent?: boolean;
}

let toastCounter = 0;

export function useToastStore() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((input: ToastInput) => {
    toastCounter += 1;
    const id = `t-${Date.now()}-${toastCounter}`;
    setToasts((prev) => [...prev, { id, ...input }]);
    return id;
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const clear = useCallback(() => setToasts([]), []);

  return { toasts, push, dismiss, clear };
}
