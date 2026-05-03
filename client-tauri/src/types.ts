export type ClientType = "lr2" | "beatoraja";

export type ClientFilter = "all" | ClientType;

export interface ClientConfig {
  api_url: string;
  bms_folders: string[];
  lr2_db_path: string | null;
  lr2_song_db_path: string | null;
  beatoraja_db_dir: string | null;
  beatoraja_songdata_db_path: string | null;
  beatoraja_songinfo_db_path: string | null;
  last_synced_at: string | null;
  client_types: ClientType[];
  refresh_token_expire_days: number;
  last_update_check_at: string | null;
  dismissed_update_id: string | null;
  dismissed_update_until: string | null;
  skipped_update_version: string | null;
  update_channel: string;
  last_update_failure_at: string | null;
  last_update_failure_version: string | null;
  last_update_failure_stage: string | null;
  last_update_failure_message: string | null;
}

export interface AuthStatus {
  logged_in: boolean;
  refresh_token_expire_days: number | null;
}

export interface UpdateAnnouncement {
  id: string;
  version: string;
  title: string;
  body_markdown: string;
  release_page_url?: string | null;
  mandatory: boolean;
  asset_size_bytes?: number | null;
  published_at?: string | null;
}

export interface UpdatePolicy {
  update_available: boolean;
  message: string | null;
  announcement?: UpdateAnnouncement | null;
}

export type SyncStage =
  | "validating"
  | "parsing"
  | "supplementing"
  | "uploading"
  | "finalizing"
  | "done";

export interface SyncRequest {
  client_filter: ClientFilter;
  full_sync: boolean;
}

export interface SyncRunHandle {
  id: string;
}

export interface SyncProgressEvent {
  sync_run_id: string;
  client?: ClientType | null;
  stage: SyncStage;
  current?: number | null;
  total?: number | null;
  message?: string | null;
}

export interface SyncSkipReason {
  code: string;
  count: number;
  message?: string | null;
}

export interface SyncErrorEntry {
  client?: ClientType | null;
  message: string;
  detail?: string | null;
}

export interface SyncResult {
  sync_run_id: string;
  finished_at: string;
  client_filter: ClientFilter;
  full_sync: boolean;
  inserted: number;
  improved: number;
  metadata_updated: number;
  unchanged: number;
  skipped_reasons: SyncSkipReason[];
  errors: SyncErrorEntry[];
  per_client?: Partial<Record<ClientType, { inserted: number; improved: number }>>;
  result_url?: string | null;
}

export type LogLevel = "info" | "warn" | "error";

export interface LogEvent {
  sync_run_id?: string | null;
  level: LogLevel;
  message: string;
  ts?: string | null;
}

export interface LogEntry {
  id: string;
  level: LogLevel;
  message: string;
  ts: string;
}

export interface UpdateDownloadProgress {
  downloaded: number;
  total?: number | null;
}

export interface UpdateError {
  stage: "check" | "download" | "verify" | "install" | "restart";
  message: string;
}

export interface PathProbe {
  path: string;
  exists: boolean;
  kind?: "file" | "dir" | null;
  size_bytes?: number | null;
}

export interface DiagnosticsInfo {
  os?: string | null;
  webview?: string | null;
  config_dir?: string | null;
  logs_dir?: string | null;
}
