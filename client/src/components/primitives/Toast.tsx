import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { useEffect } from "react";
import type { Toast } from "../../hooks/use-toast";

const TONE_ICON = {
  info: Info,
  success: CheckCircle2,
  warn: AlertTriangle,
  error: XCircle,
} as const;

export function ToastStack({
  toasts,
  onDismiss,
}: {
  toasts: Toast[];
  onDismiss: (id: string) => void;
}) {
  return (
    <div className="toast-stack" role="region" aria-label="알림">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: string) => void }) {
  const Icon = TONE_ICON[toast.tone ?? "info"];

  useEffect(() => {
    if (toast.persistent) return;
    const ms = toast.durationMs ?? 4500;
    const timer = window.setTimeout(() => onDismiss(toast.id), ms);
    return () => window.clearTimeout(timer);
  }, [toast, onDismiss]);

  return (
    <div className={`toast toast-${toast.tone ?? "info"}`} role="status">
      <Icon size={18} aria-hidden="true" />
      <div className="toast-body">
        {toast.title ? <div className="toast-title">{toast.title}</div> : null}
        <div className="toast-msg">{toast.message}</div>
      </div>
      <button type="button" className="toast-close" onClick={() => onDismiss(toast.id)} aria-label="알림 닫기">
        <X size={14} />
      </button>
    </div>
  );
}
