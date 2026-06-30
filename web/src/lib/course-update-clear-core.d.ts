export interface CourseClearDisplayState {
  clear_type: number | null;
}

export interface CourseClearDisplayInput {
  clear?: { prev: number | null; new: number | null } | null;
  previousState?: CourseClearDisplayState | null;
  currentState?: CourseClearDisplayState | null;
}

export interface CourseClearDisplay {
  previous: number | null;
  current: number | null;
  changed: boolean;
}

export function resolveCourseClearDisplay(input: CourseClearDisplayInput): CourseClearDisplay;
