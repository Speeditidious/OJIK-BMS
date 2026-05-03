import { listen, type UnlistenFn } from "@tauri-apps/api/event";

import { isTauriRuntime } from "../tauri";

export type TauriEventName =
  | "sync:started"
  | "sync:progress"
  | "sync:log"
  | "sync:finished"
  | "sync:error"
  | "sync:cancelled"
  | "update:available"
  | "update:download-progress"
  | "update:installing"
  | "update:error"
  | "auth:changed"
  | "auth:reauth-required";

type Handler<T> = (payload: T) => void;

const browserListeners = new Map<string, Set<Handler<unknown>>>();

export async function subscribe<T>(event: TauriEventName, handler: Handler<T>): Promise<UnlistenFn> {
  if (!isTauriRuntime()) {
    let bucket = browserListeners.get(event);
    if (!bucket) {
      bucket = new Set();
      browserListeners.set(event, bucket);
    }
    bucket.add(handler as Handler<unknown>);
    return () => {
      bucket?.delete(handler as Handler<unknown>);
    };
  }
  return listen<T>(event, (e) => handler(e.payload));
}

/** For browser-mode demos: emit a synthetic event to all subscribed listeners. */
export function emitBrowserEvent<T>(event: TauriEventName, payload: T) {
  if (isTauriRuntime()) return;
  const bucket = browserListeners.get(event);
  if (!bucket) return;
  bucket.forEach((handler) => {
    try {
      handler(payload);
    } catch {
      /* swallow demo errors */
    }
  });
}
