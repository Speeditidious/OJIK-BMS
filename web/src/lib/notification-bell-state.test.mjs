import test from "node:test";
import assert from "node:assert/strict";
import {
  getLatestNotificationTimestamp,
  shouldShowNotificationBellIndicator,
} from "./notification-bell-state.mjs";

test("shouldShowNotificationBellIndicator stays hidden for dismissed unread notifications", () => {
  assert.equal(
    shouldShowNotificationBellIndicator({
      unreadCount: 3,
      dismissedAt: "2026-05-19T12:00:00.000Z",
      latestUnreadAt: "2026-05-19T11:59:59.000Z",
    }),
    false,
  );
});

test("shouldShowNotificationBellIndicator lights for newer unread notifications", () => {
  assert.equal(
    shouldShowNotificationBellIndicator({
      unreadCount: 1,
      dismissedAt: "2026-05-19T12:00:00.000Z",
      latestUnreadAt: "2026-05-19T12:00:01.000Z",
    }),
    true,
  );
});

test("getLatestNotificationTimestamp returns the newest valid created_at value", () => {
  assert.equal(
    getLatestNotificationTimestamp([
      { created_at: "2026-05-19T11:00:00.000Z" },
      { created_at: "2026-05-19T12:30:00.000Z" },
      { created_at: "not-a-date" },
      { created_at: "2026-05-19T12:00:00.000Z" },
    ]),
    "2026-05-19T12:30:00.000Z",
  );
});

