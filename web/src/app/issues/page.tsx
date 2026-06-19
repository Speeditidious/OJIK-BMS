"use client";

import { Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useTranslation } from "react-i18next";
import { CircleDot, MessageSquare, Pin, Search, Plus, ShieldCheck } from "lucide-react";
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
  ISSUE_STATUS_META,
  ISSUE_STATUS_ORDER,
  IssueStatusBadge,
} from "@/components/issues/IssueStatusBadge";
import { cn } from "@/lib/utils";
import { resolveTagBadgeStyle } from "@/lib/tag-color";
import { useIssueCounts, useIssues, useIssueTags } from "@/hooks/use-issues";
import { useAuthStore } from "@/stores/auth";
import { timeAgo } from "@/lib/time";
import type {
  Issue,
  IssueSearchField,
  IssueSortKey,
  IssueStatus,
  IssueStatusCounts,
  IssueTag,
} from "@/types";

const ALL_STATUS_VALUE = "all";
const SORT_KEYS: IssueSortKey[] = ["last_activity", "created"];
const DEFAULT_SORT: IssueSortKey = "last_activity";

function isSortKey(value: string | null): value is IssueSortKey {
  return value !== null && (SORT_KEYS as string[]).includes(value);
}

const ALL_TAGS_VALUE = "__all_tags__";

function getTagName(tag: IssueTag, locale: string): string {
  if (locale === "en") return tag.name_en ?? tag.name;
  if (locale === "ja") return tag.name_ja ?? tag.name;
  return tag.name;
}

function TagBadge({ tag, locale, className }: { tag: IssueTag; locale: string; className?: string }) {
  const name = getTagName(tag, locale);
  const { background, border, text } = resolveTagBadgeStyle(tag.color, {
    slug: tag.slug,
    name: tag.name,
  });
  return (
    <span
      className={cn("inline-flex items-center rounded-full border text-[10px] px-1.5 py-0.5 leading-none shrink-0 font-semibold", className)}
      style={{ backgroundColor: background, borderColor: border, color: text }}
    >
      {name}
    </span>
  );
}

function AdminBadge() {
  const { t } = useTranslation();
  return (
    <span
      title={t("issues.admin")}
      className="inline-flex items-center justify-center"
      aria-label={t("issues.admin")}
    >
      <ShieldCheck className="h-3.5 w-3.5 text-primary shrink-0" />
    </span>
  );
}

function IssueRow({ issue, locale, backHref }: { issue: Issue; locale: string; backHref?: string }) {
  const { t } = useTranslation();
  const detailHref = backHref
    ? `/issues/${issue.id}?back=${encodeURIComponent(backHref)}`
    : `/issues/${issue.id}`;

  return (
    <a
      href={detailHref}
      className={cn(
        "flex items-start gap-3 p-4 hover:bg-muted/50 transition-colors group",
        issue.is_pinned && "bg-primary/5 hover:bg-primary/10",
      )}
    >
      <div className="mt-0.5 shrink-0 flex items-center gap-1.5">
        {issue.is_pinned && <Pin className="h-3.5 w-3.5 text-primary rotate-45" />}
        <IssueStatusBadge status={issue.status} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <TagBadge tag={issue.tag} locale={locale} />
          <span className="font-medium text-foreground group-hover:text-primary transition-colors leading-snug">
            {issue.title}
          </span>
        </div>
        <p className="text-label text-muted-foreground mt-0.5 flex items-center gap-1 flex-wrap">
          #{issue.id}
          {" · "}
          <span className="inline-flex items-center gap-1">
            {issue.author.is_admin && <AdminBadge />}
            {t("issues.list.openedBy", { username: issue.author.username })}
          </span>
          {" · "}
          {t("issues.list.created")} {timeAgo(issue.created_at, t)}
          {" · "}
          {t("issues.list.updated")} {timeAgo(issue.last_activity_at, t)}
        </p>
      </div>
      {issue.comment_count > 0 && (
        <div className="shrink-0 flex items-center gap-1 text-label text-muted-foreground">
          <MessageSquare className="h-3.5 w-3.5" />
          {issue.comment_count}
        </div>
      )}
    </a>
  );
}

function IssueListContent() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuthStore();

  const page = Number(searchParams.get("page") ?? "1");
  const q = searchParams.get("q") ?? undefined;
  const searchField = (searchParams.get("search_field") ?? "all") as IssueSearchField;
  const tag = searchParams.get("tag") ?? undefined;
  const status = (searchParams.get("status") ?? "open") as IssueStatus | "all";
  const sortParam = searchParams.get("sort");
  const sort: IssueSortKey = isSortKey(sortParam) ? sortParam : DEFAULT_SORT;

  const { data: tags } = useIssueTags();
  const { data, isLoading } = useIssues({
    page,
    size: 20,
    q,
    search_field: searchField,
    tag,
    status,
    sort,
  });
  const { data: counts } = useIssueCounts({ q, search_field: searchField, tag });

  function navigate(params: Record<string, string | undefined>) {
    const sp = new URLSearchParams(searchParams.toString());
    Object.entries(params).forEach(([k, v]) => {
      if (v === undefined || v === "") sp.delete(k);
      else sp.set(k, v);
    });
    sp.set("page", "1");
    router.push(`/issues?${sp.toString()}`);
  }

  return (
    <div className="container max-w-4xl py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <CircleDot className="h-7 w-7 text-primary" />
          <h1 className="text-3xl font-bold">{t("issues.title")}</h1>
        </div>
        {user && (
          <Button asChild size="sm">
            <Link href="/issues/new">
              <Plus className="h-4 w-4 mr-1" />
              {t("issues.newIssue")}
            </Link>
          </Button>
        )}
      </div>

      {/* Notice */}
      <div className="rounded-lg border bg-muted/30 p-4 space-y-2 text-label text-muted-foreground">
        <p>{t("issues.notice")}</p>
        <p>{t("issues.noticeManners")}</p>
      </div>

      {/* Search & Filter bar */}
      <div className="flex flex-col sm:flex-row gap-2">
        <div className="relative flex-1 flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
            <Input
              id="issue-search-input"
              className="pl-9"
              placeholder={t("issues.searchPlaceholder")}
              defaultValue={q}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  navigate({ q: (e.target as HTMLInputElement).value || undefined });
                }
              }}
            />
          </div>
          <Button
            size="sm"
            variant="secondary"
            className="shrink-0"
            onClick={() => {
              const input = document.getElementById("issue-search-input") as HTMLInputElement | null;
              navigate({ q: input?.value || undefined });
            }}
          >
            <Search className="h-4 w-4" />
          </Button>
        </div>

        <Select value={searchField} onValueChange={(v) => navigate({ search_field: v })}>
          <SelectTrigger className="w-36 shrink-0">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("issues.searchField.all")}</SelectItem>
            <SelectItem value="title">{t("issues.searchField.title")}</SelectItem>
            <SelectItem value="body">{t("issues.searchField.body")}</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={tag ?? ALL_TAGS_VALUE}
          onValueChange={(v) => navigate({ tag: v === ALL_TAGS_VALUE ? undefined : v })}
        >
          <SelectTrigger className="w-32 shrink-0">
            <SelectValue placeholder={t("issues.allTags")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_TAGS_VALUE}>{t("issues.allTags")}</SelectItem>
            {tags?.map((tg) => (
              <SelectItem key={tg.id} value={tg.slug}>
                {getTagName(tg, i18n.language)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={sort}
          onValueChange={(v) => navigate({ sort: v === DEFAULT_SORT ? undefined : v })}
        >
          <SelectTrigger className="w-40 shrink-0" aria-label={t("issues.sort.label")}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SORT_KEYS.map((key) => (
              <SelectItem key={key} value={key}>
                {t(`issues.sort.${key}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Status filter pills */}
      <TooltipProvider delayDuration={200}>
        <div className="flex gap-2 flex-wrap">
          {ISSUE_STATUS_ORDER.map((s) => {
            const active = status === s;
            const meta = ISSUE_STATUS_META[s];
            const Icon = meta.icon;
            const count = counts ? counts[s as keyof IssueStatusCounts] : undefined;
            return (
              <Tooltip key={s}>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    onClick={() => navigate({ status: active ? ALL_STATUS_VALUE : s })}
                    aria-pressed={active}
                    className={cn(
                      "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-label font-medium transition-colors border",
                      active
                        ? meta.pillActiveClass
                        : "bg-transparent border-border text-muted-foreground hover:border-muted-foreground hover:text-foreground",
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {t(`issues.status.${s}`)}
                    {count !== undefined && (
                      <span
                        className={cn(
                          "ml-1 tabular-nums text-[11px]",
                          active ? "opacity-80" : "text-muted-foreground/80",
                        )}
                      >
                        {count}
                      </span>
                    )}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-xs text-label leading-snug">
                  {t(`issues.statusTooltip.${s}`)}
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>
      </TooltipProvider>

      {/* Issue list */}
      <div className="rounded-lg border overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground">{t("common.status.loading")}</div>
        ) : !data || data.items.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">{t("issues.list.empty")}</div>
        ) : (
          <div className="divide-y">
            {data.items.map((issue) => (
              <IssueRow
                key={issue.id}
                issue={issue}
                locale={i18n.language}
                backHref={`/issues?${searchParams.toString()}`}
              />
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => navigate({ page: String(page - 1) })}
          >
            &lsaquo;
          </Button>
          <span className="text-label text-muted-foreground">
            {t("pagination.label", { page, totalPages: data.pages })}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= data.pages}
            onClick={() => navigate({ page: String(page + 1) })}
          >
            &rsaquo;
          </Button>
        </div>
      )}

      {!user && (
        <p className="text-center text-label text-muted-foreground">
          <Link href="/login" className="text-primary underline">
            {t("issues.create.loginButton")}
          </Link>
          {" "}{t("issues.create.loginRequired")}
        </p>
      )}
    </div>
  );
}

export default function IssuesPage() {
  return (
    <>
      <Navbar />
      <Suspense fallback={null}>
        <IssueListContent />
      </Suspense>
    </>
  );
}
