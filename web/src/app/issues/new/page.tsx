"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useTranslation } from "react-i18next";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MarkdownContent } from "@/components/common/MarkdownContent";
import { useIssueTags, useCreateIssue, useSearchIssueUsers, useSearchIssues } from "@/hooks/use-issues";
import { getMentionAutocompleteTrigger } from "@/lib/mention-autocomplete-core.mjs";
import { useAuthStore } from "@/stores/auth";
import type { IssueTag } from "@/types";

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

// ── Tag selector ──────────────────────────────────────────────────────────────

function TagSelector({
  tags,
  value,
  onChange,
  locale,
}: {
  tags: IssueTag[];
  value: string;
  onChange: (v: string) => void;
  locale: string;
}) {
  const { t } = useTranslation();
  return (
    <div className="space-y-1">
      <label className="text-label font-medium text-foreground">{t("issues.create.tagLabel")}</label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue placeholder={t("issues.allTags")} />
        </SelectTrigger>
        <SelectContent>
          {tags.map((tag) => {
            const name =
              locale === "en"
                ? tag.name_en ?? tag.name
                : locale === "ja"
                ? tag.name_ja ?? tag.name
                : tag.name;
            return (
              <SelectItem key={tag.id} value={tag.id}>
                {name}
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>
    </div>
  );
}

// ── Body editor with mention autocomplete ─────────────────────────────────────

function BodyEditor({
  body,
  placeholder,
  onChange,
}: {
  body: string;
  placeholder: string;
  onChange: (v: string) => void;
}) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<"edit" | "preview">("edit");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { type, users, issues } = useMentionAutocomplete(body);

  function insertMention(insert: string) {
    const el = textareaRef.current;
    if (!el) return;
    const cursor = el.selectionStart;
    const before = body.slice(0, cursor);
    const after = body.slice(cursor);
    // Replace the trailing @prefix or #prefix
    const replaced = before
      .replace(/(@[\p{L}\p{N}_]*(?:[._-][\p{L}\p{N}_]+)*)$/u, insert)
      .replace(/(#[0-9]*)$/, insert);
    onChange(replaced + after);
  }

  return (
    <div className="space-y-1">
      <label className="text-label font-medium text-foreground">{t("issues.create.bodyLabel")}</label>
      <div className="rounded-lg border overflow-hidden">
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

        {activeTab === "edit" ? (
          <div className="relative">
            <Textarea
              ref={textareaRef}
              value={body}
              onChange={(e) => onChange(e.target.value)}
              placeholder={placeholder}
              className="min-h-48 rounded-none border-0 resize-none focus-visible:ring-0"
              rows={10}
            />
            {/* Autocomplete dropdown */}
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
        ) : (
          <div className="min-h-48 p-4">
            {body ? (
              <MarkdownContent>{body}</MarkdownContent>
            ) : (
              <p className="text-muted-foreground text-label italic">
                {t("issues.create.bodyPlaceholder")}
              </p>
            )}
          </div>
        )}
      </div>
      {/* Writing tip */}
      <p className="text-[11px] text-muted-foreground">{t("issues.writingTip")}</p>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function NewIssuePage() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const { user } = useAuthStore();

  const { data: tags } = useIssueTags();
  const createIssue = useCreateIssue();

  const [tagId, setTagId] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");

  const selectedTag = tags?.find((t) => t.id === tagId);
  const bodyPlaceholder = selectedTag?.content_hint ?? t("issues.create.bodyPlaceholder");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!tagId || !title.trim() || !body.trim()) return;
    try {
      const issue = await createIssue.mutateAsync({ tag_id: tagId, title: title.trim(), body: body.trim() });
      window.location.assign(`/issues/${issue.id}`);
    } catch {
      // Error handled by mutation state
    }
  }

  return (
    <>
      <Navbar />
      <div className="container max-w-3xl py-8 space-y-6">
        <h1 className="text-h2 font-bold text-foreground">{t("issues.create.title")}</h1>

        {!user ? (
          <div className="rounded-lg border p-8 text-center space-y-4">
            <p className="text-muted-foreground">{t("issues.create.loginRequired")}</p>
            <Button asChild>
              <Link href="/login">{t("issues.create.loginButton")}</Link>
            </Button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <TagSelector
              tags={tags ?? []}
              value={tagId}
              onChange={setTagId}
              locale={i18n.language}
            />

            <div className="space-y-1">
              <label htmlFor="issue-title" className="text-label font-medium text-foreground">{t("issues.create.titleLabel")}</label>
              <Input
                id="issue-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={200}
                required
              />
            </div>

            <BodyEditor
              body={body}
              placeholder={bodyPlaceholder}
              onChange={setBody}
            />

            {createIssue.isError && (
              <p className="text-destructive text-label">
                {(createIssue.error as Error)?.message ?? t("common.states.loadFailed")}
              </p>
            )}

            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => router.back()}>
                {t("common.actions.cancel")}
              </Button>
              <Button
                type="submit"
                disabled={!tagId || !title.trim() || !body.trim() || createIssue.isPending}
              >
                {createIssue.isPending ? t("issues.create.submitting") : t("issues.create.submit")}
              </Button>
            </div>
          </form>
        )}
      </div>
    </>
  );
}
