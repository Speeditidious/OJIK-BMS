export function getLatestNotificationTimestamp(items) {
  let latest = null;
  let latestTime = Number.NEGATIVE_INFINITY;

  for (const item of items ?? []) {
    const createdAt = item?.created_at;
    if (typeof createdAt !== "string") continue;

    const time = Date.parse(createdAt);
    if (!Number.isFinite(time) || time <= latestTime) continue;

    latest = new Date(time).toISOString();
    latestTime = time;
  }

  return latest;
}

export function shouldShowNotificationBellIndicator({
  unreadCount,
  dismissedAt,
  latestUnreadAt,
}) {
  if (unreadCount <= 0) return false;
  if (!dismissedAt) return true;
  if (!latestUnreadAt) return false;

  return Date.parse(latestUnreadAt) > Date.parse(dismissedAt);
}

