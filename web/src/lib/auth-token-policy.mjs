export function getRefreshFailureKind(status) {
  if (status === 401 || status === 403) return "invalid";
  return "unavailable";
}

export function shouldClearTokensForFetchUserError(error) {
  return error instanceof Error && error.message === "Authentication required";
}
