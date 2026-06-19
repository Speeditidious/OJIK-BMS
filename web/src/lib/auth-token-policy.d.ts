export function getRefreshFailureKind(status: number): "invalid" | "unavailable";

export function shouldClearTokensForFetchUserError(error: unknown): boolean;
