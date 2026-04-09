// ── User types ───────────────────────────────────────────────────────────────

export interface User {
  id: string;
  username: string;
  is_active: boolean;
  is_public: boolean;
}

export interface OAuthAccount {
  id: number;
  provider: string;
  provider_username: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// ── Score types ───────────────────────────────────────────────────────────────

export type ClientType = "lr2" | "beatoraja" | "qwilight";

export interface UserScore {
  id: string;
  user_id: string;
  scorehash: string | null;
  fumen_sha256: string | null;
  fumen_md5: string | null;
  fumen_hash_others: string | null;
  client_type: ClientType;
  clear_type: number | null;
  exscore: number | null;
  rate: number | null;
  rank: string | null;
  max_combo: number | null;
  min_bp: number | null;
  play_count: number | null;
  clear_count: number | null;
  judgments: Record<string, number> | null;
  options: Record<string, unknown> | null;
  recorded_at: string | null;
  synced_at: string | null;
  is_first_sync: boolean;
}

/** Per-field best score aggregated from each client's latest row — used by GET /scores/me/{sha256}. */
export interface PerFieldBestScore {
  best_clear_type: number | null;
  best_clear_type_client: string | null;
  best_exscore: number | null;
  rate: number | null;
  rank: string | null;
  best_exscore_client: string | null;
  best_min_bp: number | null;
  best_min_bp_client: string | null;
  best_max_combo: number | null;
  best_max_combo_client: string | null;
  /** "LR", "BR", "MIX", or null */
  source_client: string | null;
  source_client_detail: Record<string, string> | null;
}

// ── Difficulty table types ────────────────────────────────────────────────────

export interface DifficultyTable {
  id: string;
  name: string;
  symbol: string | null;
  slug: string | null;
  source_url: string | null;
  is_default: boolean;
  updated_at: string;
  song_count: number | null;
}

export interface DifficultyTableDetail extends DifficultyTable {
  level_order: string[];
}

/** Per-field best user scores attached to a TableFumen row. */
export interface TableFumenScore {
  best_clear_type: number | null;
  best_exscore: number | null;
  rate: number | null;
  rank: string | null;
  best_min_bp: number | null;
  /** "LR", "BR", "MIX", or null */
  source_client: string | null;
  source_client_detail: Record<string, string> | null;
  options: Record<string, unknown> | null;
  client_type: string | null;
  play_count: number | null;
}

export interface UserTag {
  id: string;
  tag: string;
}

export interface TableFumen {
  level: string;
  md5: string | null;
  sha256: string | null;
  title: string | null;
  artist: string | null;
  file_url: string | null;
  file_url_diff: string | null;
  bpm_main: number | null;
  bpm_min: number | null;
  bpm_max: number | null;
  notes_total: number | null;
  notes_n: number | null;
  notes_ln: number | null;
  notes_s: number | null;
  notes_ls: number | null;
  total: number | null;
  length: number | null;
  youtube_url: string | null;
  table_entries: Array<{ table_id: string; level: string }> | null;
  user_score: TableFumenScore | null;
  user_tags: UserTag[];
}

export interface FumenDetail {
  md5: string | null;
  sha256: string | null;
  title: string | null;
  artist: string | null;
  bpm_min: number | null;
  bpm_max: number | null;
  bpm_main: number | null;
  notes_total: number | null;
  notes_n: number | null;
  notes_ln: number | null;
  notes_s: number | null;
  notes_ls: number | null;
  total: number | null;
  length: number | null;
  youtube_url: string | null;
  file_url: string | null;
  file_url_diff: string | null;
  table_entries: Array<{ table_id: string; level: string }> | null;
}

export interface CustomTable {
  id: string;
  owner_id: string;
  name: string;
  is_public: boolean;
  levels: unknown[] | null;
}

export interface CustomCourse {
  id: string;
  owner_id: string;
  name: string;
  song_list: string[] | null;
  course_file_config: Record<string, unknown> | null;
}

// ── Schedule types ────────────────────────────────────────────────────────────

export interface Schedule {
  id: string;
  user_id: string;
  title: string;
  description: string | null;
  scheduled_date: string | null;
  scheduled_time: string | null;
  is_completed: boolean;
}

// ── API utility types ─────────────────────────────────────────────────────────

export interface Pagination<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface MessageResponse {
  message: string;
}

export interface ApiError {
  detail: string;
}

// ── Analysis types ────────────────────────────────────────────────────────────

export interface PlaySummary {
  total_scores: number;
  clear_type_breakdown: Record<string, number>;
}

export interface GradeDistributionItem {
  clear_type: number | null;
  count: number;
}

export interface ScoreTrendItem {
  played_at: string | null;
  score: number | null;
  clear_type: number | null;
  min_bp: number | null;
}

// ── Score update types (GET /analysis/score-updates) ─────────────────────────

export interface TableLevelRef {
  symbol: string;
  slug: string;
  level: string;
}

export interface CurrentState {
  clear_type: number | null;
  exscore: number | null;
  rate: number | null;
  rank: string | null;
  min_bp: number | null;
  max_combo: number | null;
}

/** Common base for all score update items. is_course=true means this is a course record. */
export interface ScoreUpdateBase {
  fumen_sha256: string | null;
  fumen_md5: string | null;
  title: string | null;
  artist: string | null;
  table_levels: TableLevelRef[];
  client_type: ClientType;
  recorded_at: string | null;
  is_course: boolean;
  is_new_play: boolean;
  course_name: string | null;
  dan_title: string | null;
  current_state: CurrentState;
  options: Record<string, unknown> | null;
}

export interface ClearTypeUpdateItem extends ScoreUpdateBase {
  prev_clear_type: number | null;
  new_clear_type: number | null;
  best_min_bp: number | null;
}

export interface ExscoreUpdateItem extends ScoreUpdateBase {
  prev_exscore: number | null;
  new_exscore: number | null;
  prev_rank: string | null;
  new_rank: string | null;
  prev_rate: number | null;
  new_rate: number | null;
  best_min_bp: number | null;
}

export interface MaxComboUpdateItem extends ScoreUpdateBase {
  prev_max_combo: number | null;
  new_max_combo: number | null;
}

export interface MinBPUpdateItem extends ScoreUpdateBase {
  prev_min_bp: number | null;
  new_min_bp: number | null;
}

export interface PlayCountUpdateItem extends ScoreUpdateBase {
  prev_play_count: number | null;
  new_play_count: number | null;
  is_initial_sync: boolean;
}

export interface ScoreUpdatesResponse {
  clear_type_updates: ClearTypeUpdateItem[];
  exscore_updates: ExscoreUpdateItem[];
  max_combo_updates: MaxComboUpdateItem[];
  min_bp_updates: MinBPUpdateItem[];
  play_count_updates: PlayCountUpdateItem[];
}
