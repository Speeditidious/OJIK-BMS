"use client";

// Minimal toast hook — wraps console output until a full toast system is wired in.
// Replace this with a proper implementation (e.g. shadcn/ui toast) when needed.

interface ToastOptions {
  description?: string;
  variant?: "default" | "destructive";
}

function toast(opts: ToastOptions) {
  if (opts.variant === "destructive") {
    console.error("[toast]", opts.description);
  } else {
    console.info("[toast]", opts.description);
  }
}

export function useToast() {
  return { toast };
}
