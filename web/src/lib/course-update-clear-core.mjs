export function resolveCourseClearDisplay({ clear, previousState, currentState }) {
  return {
    previous: clear ? clear.prev : (previousState?.clear_type ?? null),
    current: clear ? clear.new : (currentState?.clear_type ?? null),
    changed: Boolean(clear && clear.prev !== clear.new),
  };
}
