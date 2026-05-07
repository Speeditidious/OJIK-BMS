import { probePath } from "../tauri";
import type { PathProbe } from "../types";

export type Validity = "empty" | "valid" | "missing" | "invalid" | "unknown";

export interface ValidityState extends PathProbe {
  validity: Validity;
  reason?: string;
}

const cache = new Map<string, Promise<ValidityState>>();

export function probeForValidity(path: string | null | undefined): Promise<ValidityState> {
  if (!path) {
    return Promise.resolve({ path: "", exists: false, validity: "empty" });
  }
  const existing = cache.get(path);
  if (existing) return existing;

  const pending = (async () => {
    const probe = await probePath(path);
    if (!probe) {
      return { path, exists: false, validity: "unknown" } satisfies ValidityState;
    }
    return {
      ...probe,
      validity: probe.exists ? "valid" : "missing",
    } satisfies ValidityState;
  })();

  cache.set(path, pending);
  // Auto-evict after 5s so changes on disk get picked up.
  window.setTimeout(() => cache.delete(path), 5000);
  return pending;
}

export function clearValidityCache(): void {
  cache.clear();
}
