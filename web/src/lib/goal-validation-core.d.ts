export interface GoalBaselineLike {
  clear_type: number | null;
  min_bp: number | null;
  rank: string | null;
  rate: number | null;
}

export interface GoalTargetLike {
  clearType?: number | null;
  minBp?: number | null;
  rank?: string | null;
  rate?: number | null;
}

export interface GoalValidation {
  ok: boolean;
  errors: string[];
  improvedMetrics: string[];
}

export declare function validateGoalTarget(baseline: GoalBaselineLike, target: GoalTargetLike): GoalValidation;
