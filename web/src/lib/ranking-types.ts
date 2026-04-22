/** Ranking system type definitions. */

export type RankingType = "exp" | "bmsforce";
export type RatingContributionMetric = "exp" | "rating";
export type RatingContributionScope = "top" | "all";
export type RatingContributionSortBy =
  | "rank"
  | "value"
  | "level"
  | "title"
  | "clear_type"
  | "min_bp"
  | "rate"
  | "rank_grade"
  | "env";
export type RatingHistoryMetric = "exp" | "rating" | "bmsforce";

export interface RankingTableConfig {
  slug: string;
  table_id: string;
  display_name: string;
  display_order: number;
  top_n: number;
  has_exp: boolean;
  has_rating: boolean;
  has_bmsforce: boolean;
  dan_decorations: string[];
}

export interface DanDecoration {
  dan_title: string;
  display_text: string;
  color: string;
  glow_intensity: "none" | "subtle" | "strong";
}

export interface RankingEntry {
  rank: number;
  user_id: string;
  username: string;
  avatar_url: string | null;
  exp: number | null;
  exp_level: number | null;
  rating: number | null;     // raw top-N sum (unstandardised)
  bms_force: number | null;  // BMSFORCE (standardised)
  dan_decoration: DanDecoration | null;
}

export interface RankingResponse {
  table_slug: string;
  display_name: string;
  type: RankingType;
  total_count: number;
  page: number;
  limit: number;
  entries: RankingEntry[];
}

export interface RankingContribution {
  hash: string;
  level: string;
  song_rating?: number;
  song_exp?: number;
  title: string;
}

export interface MyRankData {
  table_slug: string;
  status: "ok" | "pending" | "no_scores";
  exp: number;
  exp_level: number;
  is_max_level: boolean;
  max_level: number;
  exp_rank: number | null;
  exp_total_users: number;
  rating: number;
  rating_rank: number | null;
  rating_total_users: number;
  bms_force: number;
  bms_force_rank: number | null;
  bms_force_total_users: number;
  last_synced_at: string | null;
  calculated_at: string | null;
  dan_decoration: DanDecoration | null;
  top_n: number;
  exp_to_next_level: number;
  exp_level_current_span: number;
  exp_level_progress_ratio: number;
  rating_contributions: RankingContribution[];
  exp_top_contributions: RankingContribution[];
}

export interface RankingContributionEntry {
  rank: number;
  previous_rank?: number | null;
  sha256: string | null;
  md5: string | null;
  title: string;
  artist: string | null;
  level: string;
  symbol: string;
  clear_type: number;
  previous_clear_type?: number | null;
  client_types: string[];
  source_client?: string | null;
  source_client_detail?: Record<string, string | null> | null;
  min_bp: number | null;
  previous_min_bp?: number | null;
  rate: number | null;
  previous_rate?: number | null;
  rank_grade: string | null;
  previous_rank_grade?: string | null;
  exscore: number | null;
  previous_exscore?: number | null;
  value: number;
  previous_value?: number | null;
  is_in_top_n: boolean;
  was_in_top_n?: boolean;
  delta_exp?: number;
  delta_rating?: number;
  updated_today?: boolean;
}

export interface RankingContributionResponse {
  table_slug: string;
  metric: RatingContributionMetric;
  scope: RatingContributionScope;
  top_n: number;
  total_count: number;
  page: number;
  limit: number;
  calculated_at: string | null;
  entries: RankingContributionEntry[];
}

export interface RankingHistoryPoint {
  date: string;
  exp: number;
  exp_level: number;
  rating: number;
  rating_norm: number;
}

export interface RankingHistoryResponse {
  table_slug: string;
  user_id: string;
  from: string;
  to: string;
  points: RankingHistoryPoint[];
}

export interface RatingBreakdownSummaryPoint {
  exp: number;
  exp_level: number;
  is_max_level: boolean;
  max_level: number;
  exp_level_progress_ratio: number;
  exp_to_next_level: number;
  exp_level_current_span: number;
  rating: number;
  rating_norm: number;
}

export interface BmsforceBreakdown {
  rating_component: number;
  level_component: number;
  total: number;
}

export interface RatingBreakdownResponse {
  date: string;
  previous: RatingBreakdownSummaryPoint;
  current: RatingBreakdownSummaryPoint;
  exp_contributions: RankingContributionEntry[];
  exp_total_entries?: number;
  rating_contributions: RankingContributionEntry[];
  rating_total_entries?: number;
  bmsforce_breakdown: BmsforceBreakdown;
}
