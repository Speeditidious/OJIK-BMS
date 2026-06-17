import type { DanDecoration } from "@/lib/ranking-types";

export interface RangeDisplay {
  text: string;
}

export interface BracketMeta {
  key: string;
  group: string | null;
  order: number;
  color: string;
  has_current: boolean;
  display_ranges: RangeDisplay[];
}

export interface CategoryMeta {
  key: string;
  name: string;
  order: number;
  brackets: BracketMeta[];
}

export interface WeeklyPeriodSummary {
  weekly_id: string;
  period_start: string;
  period_end: string;
}

export interface WeeklyRolloverInfo {
  timezone: string;
  day_of_week: string;
  hour: number;
  minute: number;
  description: string;
}

export interface RecordSnapshot {
  clear_type: number | null;
  exscore: number | null;
  rate: number | null;
  rank: string | null;
  min_bp: number | null;
  effective_ts: string | null;
}

export interface RecordImprovement {
  is_first_record: boolean;
  clear_type_changed: boolean;
  exscore_delta: number | null;
  min_bp_delta: number | null;
  rate_delta: number | null;
  rank_changed: boolean;
  previous: RecordSnapshot | null;
  current: RecordSnapshot;
}

export interface MyRecord {
  dan_decoration: DanDecoration | null;
  score_id: string | null;
  clear_type: number | null;
  exscore: number | null;
  rate: number | null;
  rank: string | null;
  min_bp: number | null;
  play_count: number | null;
  options: Record<string, unknown> | null;
  client_type: string | null;
  improved: boolean;
  improvement: RecordImprovement | null;
}

export interface WeeklyFumenItem {
  fumen_id: string;
  slot: number;
  table_symbol: string | null;
  level: string;
  title: string | null;
  artist: string | null;
  sha256: string | null;
  md5: string | null;
  my_record: MyRecord | null;
}

export interface WeeklyDetail {
  weekly_id: string;
  category_key: string;
  bracket_key: string;
  bracket_group: string | null;
  color: string;
  period_start: string;
  period_end: string;
  is_current: boolean;
  fumens: WeeklyFumenItem[];
}

export interface PlayerRecord {
  user_id: string;
  username: string;
  avatar_url: string | null;
  dan_decoration: DanDecoration | null;
  score_id: string | null;
  clear_type: number | null;
  exscore: number | null;
  rate: number | null;
  rank: string | null;
  min_bp: number | null;
  play_count: number | null;
  options: Record<string, unknown> | null;
  client_type: string | null;
  improved: boolean;
  improvement: RecordImprovement | null;
}

export interface WeeklyFumenRecords {
  weekly_id: string;
  fumen_id: string;
  records: PlayerRecord[];
  next_offset: number | null;
}
