"use client";

import { Suspense, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, CheckCheck, Download, Megaphone, Trash2 } from "lucide-react";
import { MarkdownContent } from "@/components/common/MarkdownContent";
import { useTranslation } from "react-i18next";
import { Pagination } from "@/components/common/Pagination";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useDeleteNotifications, useMarkAllRead, useMarkRead, useNotifications } from "@/hooks/use-notifications";
import { formatRelativeTime } from "@/lib/relative-time";
import { cn } from "@/lib/utils";
import type { NotificationItem } from "@/types";

function NotificationTypeIcon({ type }: { type: string }) {
  if (type === "announcement") {
    return (
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/15">
        <Megaphone className="h-4 w-4 text-accent" />
      </div>
    );
  }
  if (type === "client_update") {
    return (
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/15">
        <Download className="h-4 w-4 text-primary" />
      </div>
    );
  }
  return (
    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary">
      <Bell className="h-4 w-4 text-muted-foreground" />
    </div>
  );
}

function NotificationRow({
  item,
  isSelected,
  locale,
  onToggle,
  onOpen,
}: {
  item: NotificationItem;
  isSelected: boolean;
  locale: string;
  onToggle: () => void;
  onOpen: () => void;
}) {
  const isUnread = !item.is_read;

  return (
    <div
      className={cn(
        "relative flex cursor-pointer items-start gap-3 border-b px-4 py-3.5 last:border-b-0 transition-colors hover:bg-secondary/40",
        isUnread
          ? "bg-primary/5 dark:bg-primary/8"
          : "opacity-70 hover:opacity-90",
        isSelected && "bg-primary/10 dark:bg-primary/12",
      )}
      onClick={onOpen}
    >
      {/* Unread indicator */}
      {isUnread && (
        <span className="absolute left-0 top-0 h-full w-0.5 rounded-r bg-primary" />
      )}

      {/* Checkbox */}
      <input
        type="checkbox"
        checked={isSelected}
        onChange={onToggle}
        className="mt-1 h-4 w-4 shrink-0 cursor-pointer accent-primary"
        onClick={(e) => e.stopPropagation()}
      />

      {/* Type icon */}
      <NotificationTypeIcon type={item.type} />

      {/* Content */}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-start gap-x-2 gap-y-0.5">
          <span
            className={cn(
              "text-body leading-snug",
              isUnread ? "font-semibold text-foreground" : "text-foreground/80",
            )}
          >
            {item.title}
          </span>
        </div>
        {item.body && (
          <div className="mt-1 line-clamp-2 overflow-hidden text-label">
            <MarkdownContent className="text-muted-foreground [&_p]:mb-0 [&_h1]:text-label [&_h1]:font-normal [&_h2]:text-label [&_h2]:font-normal [&_h3]:text-label [&_h3]:font-normal">
              {item.body}
            </MarkdownContent>
          </div>
        )}
        <p className="mt-1.5 text-caption text-muted-foreground/70">
          {formatRelativeTime(item.created_at, locale)}
        </p>
      </div>
    </div>
  );
}

function NotificationsContent() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [type, setType] = useState("all");
  const [keyword, setKeyword] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const { data } = useNotifications({
    page,
    size: 20,
    type: type === "all" ? undefined : type,
    keyword: keyword || undefined,
  });
  const markRead = useMarkRead();
  const markAllRead = useMarkAllRead();
  const deleteNotifications = useDeleteNotifications();
  const selectedSet = useMemo(() => new Set(selected), [selected]);

  const allIds = data?.items.map((item) => item.id) ?? [];
  const allSelected = allIds.length > 0 && selected.length === allIds.length;
  const toggleAll = () => setSelected(allSelected ? [] : allIds);

  const toggleItem = (id: string) =>
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );

  const openNotification = (id: string, linkUrl: string | null) => {
    markRead.mutate([id]);
    if (linkUrl) router.push(linkUrl);
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container mx-auto px-4 py-8">
        {/* Page header */}
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/12 text-primary">
            <Bell className="h-5 w-5" />
          </div>
          <h1 className="text-3xl font-bold">{t("notifications.page.title")}</h1>
        </div>

        {/* Filter bar */}
        <div className="mb-4 flex flex-col gap-2 sm:flex-row">
          <Select value={type} onValueChange={(v) => { setType(v); setPage(1); }}>
            <SelectTrigger className="sm:w-52">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("notifications.filters.all")}</SelectItem>
              <SelectItem value="announcement">{t("notifications.filters.announcement")}</SelectItem>
              <SelectItem value="client_update">{t("notifications.filters.clientUpdate")}</SelectItem>
              <SelectItem value="issue_mention">{t("notifications.filters.issueMention")}</SelectItem>
            </SelectContent>
          </Select>

          <Input
            value={keyword}
            onChange={(e) => { setKeyword(e.target.value); setPage(1); }}
            placeholder={t("notifications.filters.keyword")}
            className="sm:max-w-xs"
          />

          {/* Bulk actions */}
          <div className="flex gap-2 sm:ml-auto">
            <Button
              variant="outline"
              size="sm"
              disabled={selected.length === 0}
              onClick={() => {
                markRead.mutate(selected);
                setSelected([]);
              }}
            >
              <CheckCheck className="mr-1.5 h-4 w-4" />
              {t("notifications.actions.markRead")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => markAllRead.mutate()}
            >
              <CheckCheck className="mr-1.5 h-4 w-4" />
              {t("notifications.actions.markAllRead")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={selected.length === 0}
              onClick={() => {
                deleteNotifications.mutate(selected);
                setSelected([]);
              }}
              className="text-destructive hover:text-destructive dark:text-destructive"
            >
              <Trash2 className="mr-1.5 h-4 w-4" />
              {t("notifications.actions.delete")}
            </Button>
          </div>
        </div>

        {/* List */}
        <div className="overflow-hidden rounded-xl border bg-card shadow-sm">
          {/* Table header */}
          <div className="flex items-center gap-3 border-b bg-muted/40 px-4 py-2.5">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAll}
              className="h-4 w-4 cursor-pointer accent-primary"
            />
            <span className="text-label font-medium text-muted-foreground">
              {t("notifications.page.list")}
            </span>
            {selected.length > 0 && (
              <span className="ml-auto text-label text-muted-foreground">
                {t("notifications.page.selected", { count: selected.length })}
              </span>
            )}
          </div>

          {data?.items.map((item) => (
            <NotificationRow
              key={item.id}
              item={item}
              isSelected={selectedSet.has(item.id)}
              locale={i18n.language}
              onToggle={() => toggleItem(item.id)}
              onOpen={() => openNotification(item.id, item.link_url)}
            />
          ))}

          {data && data.items.length === 0 && (
            <div className="flex flex-col items-center gap-3 py-16 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                <Bell className="h-6 w-6 text-muted-foreground" />
              </div>
              <p className="text-body text-muted-foreground">{t("notifications.page.empty")}</p>
            </div>
          )}
        </div>

        {data && data.pages > 1 && (
          <div className="mt-6">
            <Pagination
              page={page}
              totalPages={data.pages}
              onPageChange={setPage}
              label={t("pagination.label", { page, totalPages: data.pages })}
              placeholder={t("pagination.placeholder")}
            />
          </div>
        )}
      </main>
    </div>
  );
}

export default function NotificationsPage() {
  return (
    <Suspense>
      <NotificationsContent />
    </Suspense>
  );
}
