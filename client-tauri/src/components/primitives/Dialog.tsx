import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

export function Dialog({
  open,
  title,
  onClose,
  closeOnBackdrop = true,
  dismissable = true,
  footer,
  children,
}: {
  open: boolean;
  title: ReactNode;
  onClose?: () => void;
  closeOnBackdrop?: boolean;
  dismissable?: boolean;
  footer?: ReactNode;
  children: ReactNode;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;

    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape" && dismissable) {
        event.preventDefault();
        onClose?.();
      }
      if (event.key === "Tab" && dialogRef.current) {
        const focusables = dialogRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }

    document.addEventListener("keydown", handleKey);
    const id = window.setTimeout(() => {
      const first = dialogRef.current?.querySelector<HTMLElement>(
        'button:not([tabindex="-1"]), [href], input, select, textarea',
      );
      first?.focus();
    }, 30);

    return () => {
      document.removeEventListener("keydown", handleKey);
      window.clearTimeout(id);
      previouslyFocused.current?.focus?.();
    };
  }, [open, onClose, dismissable]);

  if (!open) return null;

  return (
    <div
      className="dialog-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && closeOnBackdrop && dismissable) {
          onClose?.();
        }
      }}
      role="presentation"
    >
      <div
        ref={dialogRef}
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === "string" ? title : undefined}
      >
        <header className="dialog-hd">
          <strong>{title}</strong>
          {dismissable ? (
            <button type="button" className="btn-ghost btn-icon btn" onClick={onClose} aria-label="닫기">
              <X size={16} />
            </button>
          ) : null}
        </header>
        <div className="dialog-bd">{children}</div>
        {footer ? <footer className="dialog-ft">{footer}</footer> : null}
      </div>
    </div>
  );
}
