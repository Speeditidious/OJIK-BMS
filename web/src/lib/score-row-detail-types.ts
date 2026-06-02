/** Judgment group entry for a single judgment key. */
export interface JudgmentGroup {
  key: string;
  count: number;
  fast: number | null;
  slow: number | null;
}

/** Full judgment breakdown for a score record. */
export interface JudgmentDetail {
  judgments: JudgmentGroup[];
  fast_total_excluding_pgreat: number | null;
  slow_total_excluding_pgreat: number | null;
}

/** Lane arrangement for one side (SP) or one hand (DP). */
export interface LaneGroup {
  side: string;
  option_label: string | null;
  lanes: number[];
}

/** Arrangement detail for a score record. */
export interface ArrangementDetail {
  option_label: string | null;
  lane_groups: LaneGroup[] | null;
  double_option_label: string | null;
  unavailable_reason: string | null;
}

/** A single score record within the row detail response. */
export interface RowDetailRecord {
  score_id: string;
  client_type: string;
  clear_type: number | null;
  min_bp: number | null;
  rate: number | null;
  rank: string | null;
  exscore: number | null;
  play_count: number | null;
  judgment_detail: JudgmentDetail | null;
  arrangement: ArrangementDetail | null;
}

/** Response from GET /scores/fumen/{fumen_id}/row-detail */
export interface FumenRowDetailResponse {
  fumen_id: string;
  keymode: number | null;
  detail_basis: string;
  records: RowDetailRecord[];
}

/** One aggregate score record for a course. */
export interface CourseRowDetailRecord {
  score_id: string;
  client_type: string;
  judgment_detail: JudgmentDetail | null;
  option_label: string | null;
}

/** One ordered stage in a course. */
export interface CourseStage {
  stage: number;
  level: string | null;
  title: string | null;
  fumen_sha256: string | null;
  fumen_md5: string | null;
  table_symbol: string | null;
}

/** Response from GET /scores/course/{course_hash}/row-detail */
export interface CourseRowDetailResponse {
  course_name: string;
  records: CourseRowDetailRecord[];
  stages: CourseStage[];
}
