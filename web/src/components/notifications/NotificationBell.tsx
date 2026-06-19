"use client";

import { Bell, Megaphone, Download } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useSyncExternalStore, useState } from "react";
import { useTranslation } from "react-i18next";
import { ClientUpdateDialog } from "@/components/notifications/ClientUpdateDialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MarkdownContent } from "@/components/common/MarkdownContent";
import { useMarkRead, useNotifications, useUnreadCount } from "@/hooks/use-notifications";
import {
  getLatestNotificationTimestamp,
  shouldShowNotificationBellIndicator,
} from "@/lib/notification-bell-state.mjs";
import { formatRelativeTime } from "@/lib/relative-time";
import { cn } from "@/lib/utils";
import type { NotificationItem } from "@/types";

interface NotificationBellProps {
  enabled: boolean;
  userId: string | null;
}

const DISMISSED_STORAGE_PREFIX = "ojik_notification_bell_dismissed_at";
const DISMISSED_CHANGE_EVENT = "ojik:notification-bell-dismissed-change";

function readDismissedAt(storageKey: string | null): string | null {
  if (!storageKey || typeof window === "undefined") return null;
  return window.localStorage.getItem(storageKey);
}

function NotificationTypeIcon({ type }: { type: string }) {
  if (type === "announcement") {
    return <Megaphone className="h-3.5 w-3.5 shrink-0 text-accent" />;
  }
  if (type === "client_update") {
    return <Download className="h-3.5 w-3.5 shrink-0 text-primary" />;
  }
  return <Bell className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />;
}

function NotificationDropdownItem({
  item,
  locale,
  onClick,
}: {
  item: NotificationItem;
  locale: string;
  onClick: () => void;
}) {
  return (
    <DropdownMenuItem
      className="flex cursor-pointer items-start gap-2.5 whitespace-normal px-3 py-2.5 focus:bg-secondary/60"
      onClick={onClick}
    >
      {/* Unread indicator dot */}
      <span
        className={cn(
          "mt-1 h-1.5 w-1.5 shrink-0 rounded-full",
          item.is_read ? "bg-transparent" : "bg-primary",
        )}
      />

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <NotificationTypeIcon type={item.type} />
          <span
            className={cn(
              "text-body leading-snug",
              item.is_read ? "text-foreground/70" : "font-semibold text-foreground",
            )}
          >
            {item.title}
          </span>
        </div>
        {item.body && (
          <div className="mt-0.5 line-clamp-2 overflow-hidden text-caption">
            <MarkdownContent className="text-muted-foreground [&_p]:mb-0 [&_h1]:text-caption [&_h1]:font-normal [&_h2]:text-caption [&_h2]:font-normal [&_h3]:text-caption [&_h3]:font-normal">
              {item.body}
            </MarkdownContent>
          </div>
        )}
        <p className="mt-1 text-caption text-muted-foreground/70">
          {formatRelativeTime(item.created_at, locale)}
        </p>
      </div>
    </DropdownMenuItem>
  );
}

export function NotificationBell({ enabled, userId }: NotificationBellProps) {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const { data: unread } = useUnreadCount(enabled);
  const { data } = useNotifications({ page: 1, size: 10, unreadOnly: true });
  const markRead = useMarkRead();
  const [dialogItem, setDialogItem] = useState<NotificationItem | null>(null);
  const unreadCount = unread?.count ?? 0;
  const storageKey = userId ? `${DISMISSED_STORAGE_PREFIX}:${userId}` : null;
  const dismissedAt = useSyncExternalStore(
    useCallback((onStoreChange) => {
      window.addEventListener(DISMISSED_CHANGE_EVENT, onStoreChange);
      return () => window.removeEventListener(DISMISSED_CHANGE_EVENT, onStoreChange);
    }, []),
    useCallback(() => readDismissedAt(storageKey), [storageKey]),
    () => null,
  );
  const latestUnreadAt = getLatestNotificationTimestamp(data?.items ?? []);
  const showIndicator = shouldShowNotificationBellIndicator({
    unreadCount,
    dismissedAt,
    latestUnreadAt,
  });
  const visibleUnreadCount = showIndicator ? unreadCount : 0;

  if (!enabled) return null;

  const handleOpenChange = (open: boolean) => {
    if (open && unreadCount > 0) {
      const nextDismissedAt = latestUnreadAt ?? new Date().toISOString();
      if (storageKey && typeof window !== "undefined") {
        window.localStorage.setItem(storageKey, nextDismissedAt);
        window.dispatchEvent(new Event(DISMISSED_CHANGE_EVENT));
      }
    }
  };

  const openNotification = (item: NotificationItem) => {
    markRead.mutate([item.id]);
    if (item.type === "client_update") {
      setDialogItem(item);
    } else {
      window.location.assign(item.link_url ?? "/notifications");
    }
  };

  return (
    <>
    <DropdownMenu onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger asChild>
        <button
          className="relative rounded-full p-2 text-white transition-colors hover:bg-white/10 dark:text-foreground dark:hover:bg-secondary"
          aria-label={t("notifications.dropdown.title")}
        >
          <Bell className="h-5 w-5" />
          {visibleUnreadCount > 0 && (
            <span className="absolute right-1 top-1 flex h-2.5 w-2.5 items-center justify-center rounded-full bg-destructive ring-2 ring-card">
              <span className="sr-only">{visibleUnreadCount}</span>
            </span>
          )}
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-80 p-0">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-3 py-2">
          <span className="text-label font-semibold text-foreground">
            {t("notifications.dropdown.title")}
          </span>
          {visibleUnreadCount > 0 && (
            <span className="rounded-full bg-primary/15 px-2 py-0.5 text-caption font-semibold text-primary">
              {visibleUnreadCount}
            </span>
          )}
        </div>

        {/* Items */}
        {data?.items.length ? (
          <div className="max-h-80 overflow-y-auto">
            {data.items.map((item) => (
              <NotificationDropdownItem
                key={item.id}
                item={item}
                locale={i18n.language}
                onClick={() => openNotification(item)}
              />
            ))}
          </div>
        ) : (
          <div className="px-3 py-8 text-center text-body text-muted-foreground">
            {t("notifications.dropdown.empty")}
          </div>
        )}

        {/* Footer */}
        <DropdownMenuSeparator className="my-0" />
        <DropdownMenuItem
          className="cursor-pointer justify-center py-2.5 text-body text-primary focus:bg-primary/8"
          onClick={() => router.push("/notifications")}
        >
          {t("notifications.dropdown.showAll")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
    <ClientUpdateDialog item={dialogItem} onClose={() => setDialogItem(null)} />
    </>
  );
}
