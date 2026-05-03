import { invoke } from "@tauri-apps/api/core";
import { open as openDialog } from "@tauri-apps/plugin-dialog";
import { openUrl } from "@tauri-apps/plugin-opener";

import type {
  AuthStatus,
  ClientConfig,
  DiagnosticsInfo,
  PathProbe,
  SyncRequest,
  SyncRunHandle,
  UpdatePolicy,
} from "./types";

const browserConfig: ClientConfig = {
  api_url: import.meta.env.DEV ? "http://localhost:8000" : "https://api.ojikbms.kr",
  bms_folders: [],
  lr2_db_path: null,
  lr2_song_db_path: null,
  beatoraja_db_dir: null,
  beatoraja_songdata_db_path: null,
  beatoraja_songinfo_db_path: null,
  last_synced_at: null,
  client_types: ["lr2", "beatoraja"],
  refresh_token_expire_days: 30,
  last_update_check_at: null,
  dismissed_update_id: null,
  dismissed_update_until: null,
  skipped_update_version: null,
  update_channel: "stable",
  last_update_failure_at: null,
  last_update_failure_version: null,
  last_update_failure_stage: null,
  last_update_failure_message: null,
};

let mockConfig: ClientConfig | null = null;

export const isTauriRuntime = () =>
  typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

export async function getConfig(): Promise<ClientConfig> {
  if (!isTauriRuntime()) {
    mockConfig ??= { ...browserConfig };
    return mockConfig;
  }
  return invoke<ClientConfig>("get_config");
}

export async function saveConfig(config: ClientConfig): Promise<ClientConfig> {
  if (!isTauriRuntime()) {
    mockConfig = { ...config };
    return mockConfig;
  }
  return invoke<ClientConfig>("save_config", { config });
}

export async function importLegacyConfig(path: string): Promise<ClientConfig> {
  if (!isTauriRuntime()) {
    return getConfig();
  }
  return invoke<ClientConfig>("import_legacy_config", { path });
}

export async function pickFile(kind: string): Promise<string | null> {
  if (!isTauriRuntime()) return null;
  const selected = await openDialog({
    multiple: false,
    directory: false,
    filters: kind.includes("config")
      ? [{ name: "JSON config", extensions: ["json"] }]
      : [{ name: "SQLite database", extensions: ["db", "sqlite", "sqlite3"] }],
  });
  return normalizeSingleSelection(selected);
}

export async function getDiagnosticsInfo(): Promise<DiagnosticsInfo> {
  if (!isTauriRuntime()) {
    return {
      os: navigator.platform || null,
      config_dir: null,
      logs_dir: null,
    };
  }
  return invoke<DiagnosticsInfo>("get_diagnostics_info");
}

export async function pickFolder(kind: string): Promise<string | null> {
  if (!isTauriRuntime()) return null;
  void kind;
  const selected = await openDialog({
    multiple: false,
    directory: true,
  });
  return normalizeSingleSelection(selected);
}

function normalizeSingleSelection(selected: string | string[] | null): string | null {
  if (Array.isArray(selected)) return selected[0] ?? null;
  return selected;
}

export async function getAuthStatus(): Promise<AuthStatus> {
  if (!isTauriRuntime()) {
    return { logged_in: false, refresh_token_expire_days: null };
  }
  return invoke<AuthStatus>("get_auth_status");
}

export async function startLogin(): Promise<AuthStatus> {
  if (!isTauriRuntime()) {
    throw new Error("Discord 로그인은 데스크톱 앱에서만 동작합니다.");
  }
  return invoke<AuthStatus>("start_login");
}

export async function logout(): Promise<AuthStatus> {
  if (!isTauriRuntime()) {
    return { logged_in: false, refresh_token_expire_days: null };
  }
  return invoke<AuthStatus>("logout");
}

export async function startSync(request: SyncRequest): Promise<SyncRunHandle> {
  if (!isTauriRuntime()) {
    return { id: `mock-${Date.now()}` };
  }
  return invoke<SyncRunHandle>("start_sync", { request });
}

export async function cancelSync(syncRunId: string): Promise<void> {
  if (!isTauriRuntime()) return;
  await invoke<void>("cancel_sync", { syncRunId });
}

export async function checkUpdatePolicy(manual: boolean): Promise<UpdatePolicy> {
  if (!isTauriRuntime()) {
    return {
      update_available: false,
      message: manual ? "브라우저 미리보기에서는 업데이트를 확인하지 않습니다." : null,
    };
  }
  return invoke<UpdatePolicy>("check_update_policy", { manual });
}

export async function installUpdate(updateId: string): Promise<void> {
  if (!isTauriRuntime()) return;
  await invoke<void>("install_update", { updateId });
}

export async function openDownloadPage(): Promise<string> {
  if (!isTauriRuntime()) {
    return "https://www.ojikbms.kr/download";
  }
  return invoke<string>("open_download_page");
}

export const SITE_URL = import.meta.env.DEV
  ? "http://localhost:3000/"
  : "https://www.ojikbms.kr/";

export async function openSite(): Promise<string> {
  if (!isTauriRuntime()) {
    window.open(SITE_URL, "_blank", "noopener,noreferrer");
    return SITE_URL;
  }
  await openUrl(SITE_URL);
  return SITE_URL;
}

/**
 * Open an external URL via the OS default browser.
 * In Tauri webview `window.open` is unreliable; this helper delegates to
 * the opener plugin which always shells out to the OS handler.
 */
export async function openExternalUrl(url: string): Promise<void> {
  const parsed = new URL(url);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error(`Unsupported external URL protocol: ${parsed.protocol}`);
  }
  const normalizedUrl = parsed.toString();
  if (!isTauriRuntime()) {
    const opened = window.open(normalizedUrl, "_blank", "noopener,noreferrer");
    if (!opened) throw new Error("Popup was blocked by the browser.");
    return;
  }
  await openUrl(normalizedUrl);
}

/**
 * Probe a filesystem path. Backend command may not exist yet (Phase 2);
 * returns null on any IPC error so the UI gracefully degrades to
 * "unknown" validity instead of blocking the user.
 */
export async function probePath(path: string): Promise<PathProbe | null> {
  if (!path) return null;
  if (!isTauriRuntime()) {
    return { path, exists: true, kind: path.endsWith("/") ? "dir" : "file" };
  }
  try {
    return await invoke<PathProbe>("probe_path", { path });
  } catch {
    return null;
  }
}

