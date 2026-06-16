"use client";

import { useState, useRef, Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useTranslation } from "react-i18next";
import { MessageSquare, ChevronDown, GitBranch, ArrowLeft, Pin, ShieldCheck, Pencil, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { resolveTagBadgeStyle } from "@/lib/tag-color";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ISSUE_STATUS_META, IssueStatusBadge } from "@/components/issues/IssueStatusBadge";
import { MarkdownContent } from "@/components/common/MarkdownContent";
import { MarkdownEditor } from "@/components/common/MarkdownEditor";
import { AvatarImage } from "@/components/common/AvatarImage";
import {
  useIssue,
  useIssueComments,
  useCreateIssueComment,
  useUpdateIssueStatus,
  useUpdateIssuePinned,
  useUpdateIssueBody,
  useUpdateIssueComment,
  useSearchIssueUsers,
  useSearchIssues,
} from "@/hooks/use-issues";
import { useAuthStore } from "@/stores/auth";
import { resolveAvatarUrl } from "@/lib/avatar";
import { getMentionAutocompleteTrigger } from "@/lib/mention-autocomplete-core.mjs";
import { timeAgo } from "@/lib/time";
import type { IssueComment as IssueCommentType, IssuePinChangeEventPayload, IssueStatus, IssueTag } from "@/types";

// Statuses where any authenticated user can still leave comments.
const COMMENTABLE_STATUSES = new Set(["open", "work_in_progress"]);

// ── Admin badge ───────────────────────────────────────────────────────────────

function AdminBadge({ label }: { label: string }) {
  return (
    <span
      title={label}
      className="inline-flex items-center justify-center"
      aria-label={label}
    >
      <ShieldCheck className="h-3.5 w-3.5 text-primary shrink-0" />
    </span>
  );
}

// ── Tag badge ─────────────────────────────────────────────────────────────────

function getTagName(tag: IssueTag, locale: string): string {
  if (locale === "en") return tag.name_en ?? tag.name;
  if (locale === "ja") return tag.name_ja ?? tag.name;
  return tag.name;
}

function TagBadge({ tag, locale }: { tag: IssueTag; locale: string }) {
  const name = getTagName(tag, locale);
  const { background, border, text } = resolveTagBadgeStyle(tag.color, {
    slug: tag.slug,
    name: tag.name,
  });
  return (
    <span
      className="inline-flex items-center rounded-full border text-[10px] px-1.5 py-0.5 leading-none font-semibold"
      style={{ backgroundColor: background, borderColor: border, color: text }}
    >
      {name}
    </span>
  );
}

// ── Author avatar ─────────────────────────────────────────────────────────────

function Avatar({
  username,
  avatarUrl,
  userId,
}: {
  username: string;
  avatarUrl: string | null;
  /** When set, the avatar becomes a link to the user's dashboard. */
  userId?: string;
}) {
  const inner = avatarUrl ? (
    <AvatarImage
      src={resolveAvatarUrl(avatarUrl)}
      alt={username}
      size={36}
      fallbackText={username}
      className="rounded-full object-cover"
    />
  ) : (
    username.charAt(0).toUpperCase()
  );

  const wrapperClass =
    "w-9 h-9 rounded-full bg-primary/20 flex items-center justify-center text-sm font-medium text-primary shrink-0 overflow-hidden";

  if (userId) {
    return (
      <Link
        href={`/users/${userId}/dashboard`}
        prefetch={false}
        aria-label={username}
        className={cn(wrapperClass, "transition-opacity hover:opacity-80")}
      >
        {inner}
      </Link>
    );
  }

  return <div className={wrapperClass}>{inner}</div>;
}

// ── Timeline entries ──────────────────────────────────────────────────────────

function StatusChangeEntry({ comment }: { comment: IssueCommentType }) {
  const { t } = useTranslation();
  const payload = comment.event_payload as { to?: string } | null;
  const toStatus = (payload?.to ?? "open") as IssueStatus;
  const meta = ISSUE_STATUS_META[toStatus];
  const Icon = meta.icon;
  return (
    <div className="flex items-center gap-2 px-3 py-1 text-label text-muted-foreground">
      <Icon className={cn("h-4 w-4 shrink-0", meta.textClass)} />
      {comment.author.is_admin && <AdminBadge label={t("issues.admin")} />}
      <span>
        {t("issues.event.statusChanged", {
          username: comment.author.username,
          status: t(`issues.status.${toStatus}`),
        })}
      </span>
      <span className="text-muted-foreground/70">· {timeAgo(comment.created_at, t)}</span>
    </div>
  );
}

function PinChangeEntry({ comment }: { comment: IssueCommentType }) {
  const { t } = useTranslation();
  const payload = comment.event_payload as IssuePinChangeEventPayload | null;
  const isPinned = payload?.is_pinned ?? false;
  return (
    <div className="flex items-center gap-2 px-3 py-1 text-label text-muted-foreground">
      <Pin className={cn("h-4 w-4 shrink-0 rotate-45", isPinned ? "text-primary" : "text-muted-foreground")} />
      {comment.author.is_admin && <AdminBadge label={t("issues.admin")} />}
      <span>
        {isPinned
          ? t("issues.event.pinned", { username: comment.author.username })
          : t("issues.event.unpinned", { username: comment.author.username })}
      </span>
      <span className="text-muted-foreground/70">· {timeAgo(comment.created_at, t)}</span>
    </div>
  );
}

function TimelineEntry({
  comment,
  issueId,
  currentUserId,
}: {
  comment: IssueCommentType;
  issueId: number;
  currentUserId: string | undefined;
}) {
  const { t } = useTranslation();
  const [isEditing, setIsEditing] = useState(false);
  const updateComment = useUpdateIssueComment(issueId, comment.id);

  const isOwnComment = currentUserId !== undefined && currentUserId === comment.author.id;
  const isEditable = isOwnComment && comment.event_type === null;

  if (comment.event_type === "status_change") {
    return <StatusChangeEntry comment={comment} />;
  }
  if (comment.event_type === "pin_change") {
    return <PinChangeEntry comment={comment} />;
  }

  const wasEdited = comment.created_at !== comment.updated_at;

  return (
    <div className="flex gap-3">
      <Avatar
        username={comment.author.username}
        avatarUrl={comment.author.avatar_url}
        userId={comment.author.id}
      />
      {isEditing ? (
        <InlineEditor
          initialBody={comment.body ?? ""}
          isSaving={updateComment.isPending}
          onCancel={() => setIsEditing(false)}
          onSave={async (body) => {
            await updateComment.mutateAsync({ body });
            setIsEditing(false);
          }}
        />
      ) : (
        <div className="flex-1 rounded-lg border overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 bg-muted/30 border-b">
            <span className="text-label font-medium text-foreground flex items-center gap-2 flex-wrap min-w-0">
              {comment.author.is_admin && <AdminBadge label={t("issues.admin")} />}
              <span className="shrink-0">{comment.author.username}</span>
              <span className="font-normal text-muted-foreground shrink-0">
                {timeAgo(comment.created_at, t)}
              </span>
              {wasEdited && (
                <span className="font-normal text-muted-foreground/70 shrink-0">
                  {t("issues.detail.editedAt", { time: timeAgo(comment.updated_at, t) })}
                </span>
              )}
            </span>
            {isEditable && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 ml-2 text-muted-foreground opacity-60 hover:opacity-100 shrink-0"
                onClick={() => setIsEditing(true)}
                aria-label={t("issues.detail.editComment")}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
          <div className="p-4">
            <MarkdownContent mentions={comment.mentions}>{comment.body ?? ""}</MarkdownContent>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Mention autocomplete ───────────────────────────────────────────────────────

function useMentionAutocomplete(body: string) {
  const trigger = getMentionAutocompleteTrigger(body);
  const type = trigger?.type ?? null;
  const userQuery = trigger?.type === "user" ? trigger.query : "";
  const issueQuery = trigger?.type === "issue" ? trigger.query : "";

  const { data: users } = useSearchIssueUsers(userQuery, type === "user");
  const { data: issues } = useSearchIssues(issueQuery, type === "issue");

  return { type, users: users ?? [], issues: issues ?? [] };
}

// ── Inline editor (issue body and comment edits — wraps MarkdownEditor) ──────

interface InlineEditorProps {
  initialBody: string;
  onSave: (body: string) => Promise<void>;
  onCancel: () => void;
  isSaving: boolean;
}

function InlineEditor({ initialBody, onSave, onCancel, isSaving }: InlineEditorProps) {
  return (
    <MarkdownEditor
      initialBody={initialBody}
      onSave={onSave}
      onCancel={onCancel}
      isSaving={isSaving}
      enableMentions={true}
      renderMentionDropdown={(body, textarea, setBody) => (
        <IssueMentionDropdown body={body} textarea={textarea} setBody={setBody} />
      )}
    />
  );
}

function IssueMentionDropdown({
  body,
  textarea,
  setBody,
}: {
  body: string;
  textarea: HTMLTextAreaElement | null;
  setBody: (v: string) => void;
}) {
  const { type, users, issues } = useMentionAutocomplete(body);

  function insertMention(insert: string) {
    const el = textarea;
    if (!el) return;
    const cursor = el.selectionStart;
    const before = body.slice(0, cursor);
    const after = body.slice(cursor);
    const replaced = before
      .replace(/(@[\p{L}\p{N}_]*(?:[._-][\p{L}\p{N}_]+)*)$/u, insert)
      .replace(/(#[0-9]*)$/, insert);
    setBody(replaced + after);
  }

  return (
    <>
      {type === "user" && users.length > 0 && (
        <div className="absolute bottom-full left-0 z-50 w-64 rounded-lg border bg-popover shadow-lg mb-1">
          {users.map((u) => (
            <button
              key={u.id}
              type="button"
              className="w-full text-left px-3 py-2 text-label hover:bg-muted transition-colors"
              onClick={() => insertMention(`@${u.username} `)}
            >
              @{u.username}
            </button>
          ))}
        </div>
      )}
      {type === "issue" && issues.length > 0 && (
        <div className="absolute bottom-full left-0 z-50 w-80 rounded-lg border bg-popover shadow-lg mb-1">
          {issues.map((iss) => (
            <button
              key={iss.id}
              type="button"
              className="w-full text-left px-3 py-2 text-label hover:bg-muted transition-colors"
              onClick={() => insertMention(`#${iss.id} `)}
            >
              <span className="text-muted-foreground">#{iss.id}</span> {iss.title}
            </button>
          ))}
        </div>
      )}
    </>
  );
}

// ── Comment box ───────────────────────────────────────────────────────────────

function CommentBox({ issueId }: { issueId: number }) {
  const { t } = useTranslation();
  const { user } = useAuthStore();
  const [body, setBody] = useState("");
  const [activeTab, setActiveTab] = useState<"edit" | "preview">("edit");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { type, users, issues } = useMentionAutocomplete(body);
  const createComment = useCreateIssueComment(issueId);

  function insertMention(insert: string) {
    const el = textareaRef.current;
    if (!el) return;
    const cursor = el.selectionStart;
    const before = body.slice(0, cursor);
    const after = body.slice(cursor);
    const replaced = before
      .replace(/(@[\p{L}\p{N}_]*(?:[._-][\p{L}\p{N}_]+)*)$/u, insert)
      .replace(/(#[0-9]*)$/, insert);
    setBody(replaced + after);
  }

  if (!user) {
    return (
      <div className="rounded-lg border p-6 text-center text-muted-foreground text-label">
        <Link href="/login" className="text-primary underline">
          {t("issues.create.loginButton")}
        </Link>{" "}
        {t("issues.detail.loginToComment")}
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      <Avatar username={user.username} avatarUrl={user.avatar_url} />
      <div className="flex-1 rounded-lg border overflow-hidden">
        {/* Tab bar */}
        <div className="flex border-b bg-muted/30">
          {(["edit", "preview"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={[
                "px-4 py-2 text-label font-medium transition-colors",
                activeTab === tab
                  ? "bg-background text-foreground border-b-2 border-primary -mb-px"
                  : "text-muted-foreground hover:text-foreground",
              ].join(" ")}
            >
              {t(tab === "edit" ? "issues.create.edit" : "issues.create.preview")}
            </button>
          ))}
        </div>

        <div className="relative">
          {activeTab === "edit" ? (
            <Textarea
              ref={textareaRef}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder={t("issues.detail.commentPlaceholder")}
              className="min-h-24 rounded-none border-0 resize-none focus-visible:ring-0"
              rows={4}
            />
          ) : (
            <div className="min-h-24 p-4">
              {body ? (
                <MarkdownContent>{body}</MarkdownContent>
              ) : (
                <p className="text-muted-foreground text-label italic">
                  {t("issues.detail.commentPlaceholder")}
                </p>
              )}
            </div>
          )}

          {/* Autocomplete */}
          {type === "user" && users.length > 0 && (
            <div className="absolute bottom-full left-0 z-50 w-64 rounded-lg border bg-popover shadow-lg mb-1">
              {users.map((u) => (
                <button
                  key={u.id}
                  type="button"
                  className="w-full text-left px-3 py-2 text-label hover:bg-muted transition-colors"
                  onClick={() => insertMention(`@${u.username} `)}
                >
                  @{u.username}
                </button>
              ))}
            </div>
          )}
          {type === "issue" && issues.length > 0 && (
            <div className="absolute bottom-full left-0 z-50 w-80 rounded-lg border bg-popover shadow-lg mb-1">
              {issues.map((iss) => (
                <button
                  key={iss.id}
                  type="button"
                  className="w-full text-left px-3 py-2 text-label hover:bg-muted transition-colors"
                  onClick={() => insertMention(`#${iss.id} `)}
                >
                  <span className="text-muted-foreground">#{iss.id}</span> {iss.title}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-end p-2 border-t bg-muted/30">
          <Button
            size="sm"
            disabled={!body.trim() || createComment.isPending}
            onClick={async () => {
              if (!body.trim()) return;
              await createComment.mutateAsync({ body: body.trim() });
              setBody("");
            }}
          >
            {createComment.isPending
              ? t("issues.detail.submittingComment")
              : t("issues.detail.submitComment")}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── Back-to-list link (reads ?back= param, requires Suspense) ─────────────────

function BackToListLink() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const back = searchParams.get("back");
  const href = back ? decodeURIComponent(back) : "/issues";
  return (
    <Link
      href={href}
      className="inline-flex items-center gap-1.5 text-label text-muted-foreground hover:text-foreground transition-colors"
    >
      <ArrowLeft className="h-3.5 w-3.5" />
      {t("issues.detail.backToList")}
    </Link>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function IssueDetailPage() {
  const { t, i18n } = useTranslation();
  const { issueId } = useParams<{ issueId: string }>();
  const id = Number(issueId);
  const { user } = useAuthStore();

  const { data: issue, isLoading } = useIssue(id);
  const { data: commentsData } = useIssueComments(id, 1, 100);
  const updateStatus = useUpdateIssueStatus(id);
  const updatePin = useUpdateIssuePinned(id);
  const [isEditingBody, setIsEditingBody] = useState(false);
  const updateIssueBody = useUpdateIssueBody(id);

  if (isLoading) {
    return (
      <>
        <Navbar />
        <div className="container max-w-4xl py-8 text-center text-muted-foreground">
          {t("common.status.loading")}
        </div>
      </>
    );
  }

  if (!issue) {
    return (
      <>
        <Navbar />
        <div className="container max-w-4xl py-8 text-center text-muted-foreground">
          {t("common.states.notFound")}
        </div>
      </>
    );
  }

  const isCommentable = COMMENTABLE_STATUSES.has(issue.status);
  const isClosed = !isCommentable;

  return (
    <>
      <Navbar />
      <div className="container max-w-4xl py-8 space-y-6">
        {/* Header */}
        <div className="space-y-3">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <h1 className="text-3xl font-bold text-foreground leading-tight">
                {issue.title}{" "}
                <span className="text-muted-foreground font-normal">#{issue.id}</span>
              </h1>
              <Suspense
                fallback={
                  <Link
                    href="/issues"
                    className="inline-flex items-center gap-1.5 text-label text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    {t("issues.detail.backToList")}
                  </Link>
                }
              >
                <BackToListLink />
              </Suspense>
            </div>
            {/* Admin controls */}
            {user?.is_admin && (
              <div className="flex items-center gap-2 shrink-0">
                {/* Pin button */}
                <Button
                  variant={issue.is_pinned ? "default" : "outline"}
                  size="sm"
                  disabled={updatePin.isPending}
                  onClick={() => updatePin.mutate({ is_pinned: !issue.is_pinned })}
                  className={cn(issue.is_pinned && "bg-primary/90 hover:bg-primary/80")}
                  title={issue.is_pinned ? t("issues.unpin") : t("issues.pin")}
                >
                  <Pin className="h-3.5 w-3.5 mr-1 rotate-45" />
                  {issue.is_pinned ? t("issues.unpin") : t("issues.pin")}
                </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="shrink-0">
                    {t("issues.detail.adminStatus.label")}
                    <ChevronDown className="h-4 w-4 ml-1" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {issue.status !== "open" && (
                    <DropdownMenuItem
                      onClick={() => updateStatus.mutate({ status: "open" })}
                    >
                      {t("issues.detail.reopen")}
                    </DropdownMenuItem>
                  )}
                  {issue.status !== "work_in_progress" && (
                    <DropdownMenuItem
                      onClick={() => updateStatus.mutate({ status: "work_in_progress" })}
                    >
                      {t("issues.detail.adminStatus.setWorkInProgress")}
                    </DropdownMenuItem>
                  )}
                  {issue.status !== "completed" && (
                    <DropdownMenuItem
                      onClick={() => updateStatus.mutate({ status: "completed" })}
                    >
                      {t("issues.detail.adminStatus.setCompleted")}
                    </DropdownMenuItem>
                  )}
                  {issue.status !== "not_planned" && (
                    <DropdownMenuItem
                      onClick={() => updateStatus.mutate({ status: "not_planned" })}
                    >
                      {t("issues.detail.adminStatus.setNotPlanned")}
                    </DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
              </div>
            )}
          </div>

          {/* Status + meta */}
          <div className="flex items-center gap-3 flex-wrap">
            <TooltipProvider delayDuration={200}>
              <IssueStatusBadge status={issue.status} withTooltip />
            </TooltipProvider>
            <TagBadge tag={issue.tag} locale={i18n.language} />
            <span className="text-label text-muted-foreground flex items-center gap-1 flex-wrap">
              {issue.author.is_admin && <AdminBadge label={t("issues.admin")} />}
              {t("issues.detail.openedBy", { username: issue.author.username })}
              {" · "}{t("issues.list.created")} {timeAgo(issue.created_at, t)}
              {" · "}{t("issues.list.updated")} {timeAgo(issue.last_activity_at, t)}
            </span>
            {isClosed && issue.closed_by && (
              <span className="text-label text-muted-foreground flex items-center gap-1">
                ·{" "}{issue.closed_by.is_admin && <AdminBadge label={t("issues.admin")} />}
                {t("issues.detail.closedBy", { username: issue.closed_by.username })}
              </span>
            )}
            <span className="text-label text-muted-foreground flex items-center gap-1">
              <MessageSquare className="h-3.5 w-3.5" />
              {t("issues.detail.comments", { count: issue.comment_count })}
            </span>
          </div>
        </div>

        {/* Issue body */}
        <div className="flex gap-3">
          <Avatar
            username={issue.author.username}
            avatarUrl={issue.author.avatar_url}
            userId={issue.author.id}
          />
          {isEditingBody ? (
            <InlineEditor
              initialBody={issue.body}
              isSaving={updateIssueBody.isPending}
              onCancel={() => setIsEditingBody(false)}
              onSave={async (body) => {
                await updateIssueBody.mutateAsync({ body });
                setIsEditingBody(false);
              }}
            />
          ) : (
            <div className="flex-1 rounded-lg border overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2 bg-muted/30 border-b">
                <span className="text-label font-medium text-foreground flex items-center gap-2 flex-wrap min-w-0">
                  {issue.author.is_admin && <AdminBadge label={t("issues.admin")} />}
                  <span className="shrink-0">{issue.author.username}</span>
                  <span className="font-normal text-muted-foreground shrink-0">
                    {timeAgo(issue.created_at, t)}
                  </span>
                  {issue.created_at !== issue.updated_at && (
                    <span className="font-normal text-muted-foreground/70 shrink-0">
                      {t("issues.detail.editedAt", { time: timeAgo(issue.updated_at, t) })}
                    </span>
                  )}
                </span>
                {user?.id === issue.author.id && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 ml-2 text-muted-foreground opacity-60 hover:opacity-100 shrink-0"
                    onClick={() => setIsEditingBody(true)}
                    aria-label={t("issues.detail.editBody")}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>
              <div className="p-4">
                <MarkdownContent mentions={issue.mentions}>{issue.body}</MarkdownContent>
              </div>
            </div>
          )}
        </div>

        {/* Comments */}
        {commentsData && commentsData.items.length > 0 && (
          <div className="space-y-4 border-t pt-4">
            {commentsData.items.map((comment) => (
              <TimelineEntry
                key={comment.id}
                comment={comment}
                issueId={id}
                currentUserId={user?.id}
              />
            ))}
          </div>
        )}

        {/* Closed notice */}
        {isClosed && (
          <div className="rounded-lg border border-border bg-muted/30 p-4 text-label text-muted-foreground text-center">
            {issue.status === "completed"
              ? t("issues.detail.closedNotice.completed")
              : t("issues.detail.closedNotice.not_planned")}
          </div>
        )}

        {/* Comment box (commentable states only — open or work_in_progress) */}
        {isCommentable && (
          <div className="space-y-3 border-t pt-4">
            <h2 className="text-base font-semibold text-foreground">
              {t("issues.detail.addComment")}
            </h2>
            <CommentBox issueId={id} />
          </div>
        )}
      </div>
    </>
  );
}
