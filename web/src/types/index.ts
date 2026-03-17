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

// ── Song types ────────────────────────────────────────────────────────────────

export interface Song {
  id: string;
  md5: string | null;
  sha256: string | null;
  title: string | null;
  artist: string | null;
  bpm: number | null;
  total_notes: number | null;
  youtube_url: string | null;
}

// ── Score types ───────────────────────────────────────────────────────────────

export type ClientType = "lr2" | "beatoraja" | "qwilight";

export interface UserScore {
  id: string;
  user_id: string;
  song_sha256: string;
  client_type: ClientType;
  clear_type: number | null;
  score_rate: number | null;
  max_combo: number | null;
  min_bp: number | null;
  play_count: number;
}

export interface ScoreHistory {
  id: string;
  user_id: string;
  song_sha256: string;
  client_type: ClientType;
  clear_type: number | null;
  old_clear_type: number | null;
  score: number | null;
  old_score: number | null;
  combo: number | null;
  old_combo: number | null;
  min_bp: number | null;
  old_min_bp: number | null;
  played_at: string | null;
}

// ── Difficulty table types ────────────────────────────────────────────────────

export interface DifficultyTable {
  id: number;
  name: string;
  symbol: string | null;
  slug: string | null;
  source_url: string | null;
  is_default: boolean;
  last_synced_at: string | null;
  song_count: number | null;
}

export interface DifficultyTableDetail extends DifficultyTable {
  level_order: string[];
}

export interface TableSong {
  level: string;
  md5: string;
  sha256: string;
  title: string;
  artist: string;
  url: string;
  extra: Record<string, unknown>;
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

// ── Chatbot types ─────────────────────────────────────────────────────────────

export interface ChatbotConversation {
  id: string;
  user_id: string | null;
  summary: string | null;
}

export interface ChatbotMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string | null;
  sources: unknown[] | null;
  token_usage: Record<string, number> | null;
  created_at: string;
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
