import type { TableLevelRef } from "@/components/common/TableLevelBadges";

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
  fumen_id: string | null;
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
  judgment_detail: import("@/lib/score-row-detail-types").JudgmentDetail | null;
  arrangement: import("@/lib/score-row-detail-types").ArrangementDetail | null;
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
  fumen_id: string;
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
  fumen_id: string;
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

// ── Fumen list types ──────────────────────────────────────────────────────────

export type FumenSearchField =
  | "title_artist" | "title" | "artist" | "level"
  | "bpm" | "notes" | "length"
  | "clear" | "bp" | "rate" | "rank" | "score" | "plays" | "option" | "env";

export type FumenSearchMode = "basic" | "regex";

export interface FumenListItem {
  fumen_id: string;
  md5: string | null;
  sha256: string | null;
  title: string | null;
  artist: string | null;
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
  file_url: string | null;
  file_url_diff: string | null;
  table_entries: Array<{ table_id: string; level: string }> | null;
  played_user_count: number;
  total_play_count: number;
  user_score: TableFumenScore | null;
  user_tags: UserTag[];
}

export interface FumenListResponse {
  items: FumenListItem[];
  total: number;
  page: number;
  limit: number;
}

export type PopularRange = "weekly" | "monthly" | "all_time";

export interface PopularFumen {
  rank: number;
  fumen_id: string;
  title: string | null;
  artist: string | null;
  sha256: string | null;
  md5: string | null;
  played_user_count: number;
  play_count: number;
}

export interface PopularFumensResponse {
  as_of: string | null;
  items: PopularFumen[];
}

// ── API utility types ─────────────────────────────────────────────────────────

export interface Pagination<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface AnnouncementTag {
  id: string;
  name: string;
  name_en: string | null;
  name_ja: string | null;
  color: string | null;
  send_notification: boolean;
  display_order: number;
}

export interface Announcement {
  id: string;
  tag: AnnouncementTag;
  title: string;
  title_en: string | null;
  title_ja: string | null;
  body: string;
  body_en: string | null;
  body_ja: string | null;
  is_published: boolean;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AnnouncementWrite {
  tag_id: string;
  title: string;
  title_en: string | null;
  title_ja: string | null;
  body: string;
  body_en: string | null;
  body_ja: string | null;
}

export interface AnnouncementTemplateWrite {
  tag_id?: string | null;
  title_template?: string;
  title_en_template?: string | null;
  title_ja_template?: string | null;
  body_template?: string;
  body_en_template?: string | null;
  body_ja_template?: string | null;
}

export interface AnnouncementTemplate {
  id: string;
  tag_id: string | null;
  title_template: string;
  title_en_template: string | null;
  title_ja_template: string | null;
  body_template: string;
  body_en_template: string | null;
  body_ja_template: string | null;
}

export interface RenderedAnnouncementTemplate {
  tag_id: string | null;
  title: string;
  title_en: string | null;
  title_ja: string | null;
  body: string;
  body_en: string | null;
  body_ja: string | null;
}

export interface NotificationItem {
  id: string;
  type: "client_update" | "announcement" | string;
  title: string;
  body: string | null;
  link_url: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
  is_read: boolean;
}

export interface TableImportQuota {
  created_limit: number;
  created_used: number;
  created_remaining: number;
  failed_limit: number;
  failed_used: number;
  failed_remaining: number;
  created_reset_at: string;
  failed_reset_at: string;
}

export interface ImportTableResponse {
  table: DifficultyTable;
  outcome: "created" | "duplicate";
  message: string;
  quota: TableImportQuota | null;
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

export type { TableLevelRef } from "@/components/common/TableLevelBadges";

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
  detail_score_id: string;
  course_hash: string | null;
  fumen_id: string | null;
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
  source_client?: string | null;
  source_client_detail?: Record<string, string | null> | null;
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

// ── Issue types ───────────────────────────────────────────────────────────────

export type IssueStatus = "open" | "work_in_progress" | "completed" | "not_planned";
export type IssueSearchField = "all" | "title" | "body";
export type IssueSortKey = "last_activity" | "created";
export type IssueCommentEventType = "status_change" | "pin_change";

export interface IssueStatusChangeEventPayload {
  from: IssueStatus;
  to: IssueStatus;
}

export interface IssueStatusCounts {
  open: number;
  work_in_progress: number;
  completed: number;
  not_planned: number;
}

export interface IssueTag {
  id: string;
  slug: string;
  name: string;
  name_en: string | null;
  name_ja: string | null;
  color: string | null;
  content_hint: string | null;
  display_order: number;
  is_active: boolean;
}

export interface IssueAuthor {
  id: string;
  username: string;
  avatar_url: string | null;
  is_admin: boolean;
}

export interface IssueMention {
  source_text: string;
  user: IssueAuthor;
}

export interface Issue {
  id: number;
  tag: IssueTag;
  status: IssueStatus;
  title: string;
  body: string;
  author: IssueAuthor;
  comment_count: number;
  last_activity_at: string;
  closed_at: string | null;
  closed_by: IssueAuthor | null;
  is_pinned: boolean;
  pinned_at: string | null;
  pinned_by: IssueAuthor | null;
  mentions: IssueMention[];
  created_at: string;
  updated_at: string;
}

export interface IssuePinChangeEventPayload {
  is_pinned: boolean;
}

export interface IssueCreate {
  tag_id: string;
  title: string;
  body: string;
}

export interface IssueComment {
  id: string;
  issue_id: number;
  author: IssueAuthor;
  body: string | null;
  created_at: string;
  updated_at: string;
  event_type: IssueCommentEventType | null;
  event_payload: IssueStatusChangeEventPayload | IssuePinChangeEventPayload | null;
  mentions: IssueMention[];
}

export interface IssueUserSearchResult {
  id: string;
  username: string;
  avatar_url: string | null;
}

export interface IssueIssueSearchResult {
  id: number;
  title: string;
  status: IssueStatus;
}
