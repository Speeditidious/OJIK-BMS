"use client";

import { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { MarkdownContent } from "@/components/common/MarkdownContent";
import {
  useAnnouncementTags,
  useCreateAnnouncement,
  useUpdateAnnouncement,
  usePublishAnnouncement,
  useRenderedAnnouncementTemplate,
  useUpsertAnnouncementTemplate,
} from "@/hooks/use-announcements";
import type { Announcement } from "@/types";

type Lang = "ko" | "en" | "ja";
type Mode = "edit" | "preview";

interface AnnouncementEditorDialogProps {
  open: boolean;
  onClose: () => void;
  announcement?: Announcement;
}

function hasContent(fields: {
  title: string;
  title_en: string;
  title_ja: string;
  body: string;
  body_en: string;
  body_ja: string;
}): boolean {
  return (
    fields.title.trim() !== "" ||
    fields.title_en.trim() !== "" ||
    fields.title_ja.trim() !== "" ||
    fields.body.trim() !== "" ||
    fields.body_en.trim() !== "" ||
    fields.body_ja.trim() !== ""
  );
}

export function AnnouncementEditorDialog({
  open,
  onClose,
  announcement,
}: AnnouncementEditorDialogProps) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;

  const isEditMode = Boolean(announcement);

  // Form state
  const [tagId, setTagId] = useState<string>("");
  const [title, setTitle] = useState("");
  const [titleEn, setTitleEn] = useState("");
  const [titleJa, setTitleJa] = useState("");
  const [body, setBody] = useState("");
  const [bodyEn, setBodyEn] = useState("");
  const [bodyJa, setBodyJa] = useState("");

  // UI state
  const [activeLang, setActiveLang] = useState<Lang>("ko");
  const [activeMode, setActiveMode] = useState<Mode>("edit");
  const [draftId, setDraftId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [pendingTemplateConfirm, setPendingTemplateConfirm] = useState(false);

  // Template fetch — only enabled when tagId is set
  const [templateTagId, setTemplateTagId] = useState<string | undefined>(undefined);
  const { data: renderedTemplate } = useRenderedAnnouncementTemplate(templateTagId);

  // Queries & mutations
  const { data: tags = [] } = useAnnouncementTags();
  const createAnnouncement = useCreateAnnouncement();
  const updateAnnouncement = useUpdateAnnouncement();
  const publishAnnouncement = usePublishAnnouncement();
  const upsertTemplate = useUpsertAnnouncementTemplate();

  // Populate from announcement when editing
  useEffect(() => {
    if (open) {
      if (announcement) {
        setTagId(announcement.tag.id);
        setTitle(announcement.title);
        setTitleEn(announcement.title_en ?? "");
        setTitleJa(announcement.title_ja ?? "");
        setBody(announcement.body);
        setBodyEn(announcement.body_en ?? "");
        setBodyJa(announcement.body_ja ?? "");
        setDraftId(announcement.id);
      } else {
        setTagId("");
        setTitle("");
        setTitleEn("");
        setTitleJa("");
        setBody("");
        setBodyEn("");
        setBodyJa("");
        setDraftId(null);
      }
      setActiveLang("ko");
      setActiveMode("edit");
      setFeedback(null);
      setPendingTemplateConfirm(false);
      setTemplateTagId(undefined);
    }
  }, [open, announcement]);

  // Show feedback briefly
  const showFeedback = useCallback((msg: string) => {
    setFeedback(msg);
    setTimeout(() => setFeedback(null), 3000);
  }, []);

  // Apply template to fields
  const applyTemplate = useCallback(
    (tpl: NonNullable<typeof renderedTemplate>) => {
      setTitle(tpl.title ?? "");
      setTitleEn(tpl.title_en ?? "");
      setTitleJa(tpl.title_ja ?? "");
      setBody(tpl.body ?? "");
      setBodyEn(tpl.body_en ?? "");
      setBodyJa(tpl.body_ja ?? "");
    },
    []
  );

  // When a new rendered template arrives and we triggered it
  const [waitingForTemplate, setWaitingForTemplate] = useState(false);
  // `applyTemplate` only calls setState and captures nothing external,
  // so omitting it from deps is intentional — its identity is stable.
  useEffect(() => {
    if (waitingForTemplate && renderedTemplate) {
      applyTemplate(renderedTemplate);
      setWaitingForTemplate(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [renderedTemplate, waitingForTemplate]);

  // Handle tag change
  const handleTagChange = (newTagId: string) => {
    setTagId(newTagId);
    const currentFields = { title, title_en: titleEn, title_ja: titleJa, body, body_en: bodyEn, body_ja: bodyJa };
    if (hasContent(currentFields)) {
      setPendingTemplateConfirm(true);
    } else {
      // Fetch and apply immediately
      setTemplateTagId(newTagId);
      setWaitingForTemplate(true);
    }
  };

  // User confirmed template overwrite
  const handleConfirmApplyTemplate = () => {
    setPendingTemplateConfirm(false);
    setTemplateTagId(tagId);
    setWaitingForTemplate(true);
  };

  // Explicit "Apply Template" button
  const handleApplyTemplate = () => {
    const currentFields = { title, title_en: titleEn, title_ja: titleJa, body, body_en: bodyEn, body_ja: bodyJa };
    if (hasContent(currentFields)) {
      setPendingTemplateConfirm(true);
    } else {
      setTemplateTagId(tagId);
      setWaitingForTemplate(true);
    }
  };

  // Build write payload
  const buildPayload = () => ({
    tag_id: tagId,
    title,
    title_en: titleEn || null,
    title_ja: titleJa || null,
    body,
    body_en: bodyEn || null,
    body_ja: bodyJa || null,
  });

  const handleSaveDraft = async () => {
    if (!tagId || !title.trim() || !body.trim()) return;
    setSaving(true);
    try {
      const payload = buildPayload();
      if (draftId) {
        await updateAnnouncement.mutateAsync({ id: draftId, data: payload });
      } else {
        const result = await createAnnouncement.mutateAsync(payload);
        setDraftId(result.id);
      }
      showFeedback(t("announcements.editor.savedDraft"));
    } finally {
      setSaving(false);
    }
  };

  const handlePublish = async () => {
    if (!tagId || !title.trim() || !body.trim()) return;
    setPublishing(true);
    try {
      // Ensure draft is saved first
      let id = draftId;
      const payload = buildPayload();
      if (!id) {
        const result = await createAnnouncement.mutateAsync(payload);
        id = result.id;
        setDraftId(id);
      } else {
        await updateAnnouncement.mutateAsync({ id, data: payload });
      }
      await publishAnnouncement.mutateAsync(id);
      showFeedback(t("announcements.editor.published"));
      onClose();
    } finally {
      setPublishing(false);
    }
  };

  const handleSaveTemplate = async () => {
    await upsertTemplate.mutateAsync({
      tag_id: tagId || null,
      title_template: title,
      title_en_template: titleEn || null,
      title_ja_template: titleJa || null,
      body_template: body,
      body_en_template: bodyEn || null,
      body_ja_template: bodyJa || null,
    });
    showFeedback(t("announcements.editor.savedTemplate"));
  };

  // Preview values with fallback
  const previewTitle =
    activeLang === "en"
      ? (titleEn || title)
      : activeLang === "ja"
        ? (titleJa || title)
        : title;
  const previewBody =
    activeLang === "en"
      ? (bodyEn || body)
      : activeLang === "ja"
        ? (bodyJa || body)
        : body;

  const currentTitle = activeLang === "ko" ? title : activeLang === "en" ? titleEn : titleJa;
  const currentBody = activeLang === "ko" ? body : activeLang === "en" ? bodyEn : bodyJa;
  const setCurrentTitle = activeLang === "ko" ? setTitle : activeLang === "en" ? setTitleEn : setTitleJa;
  const setCurrentBody = activeLang === "ko" ? setBody : activeLang === "en" ? setBodyEn : setBodyJa;

  const getTagDisplayName = (item: (typeof tags)[0]) =>
    lang.startsWith("en")
      ? (item.name_en ?? item.name)
      : lang.startsWith("ja")
        ? (item.name_ja ?? item.name)
        : item.name;

  const canSave = Boolean(tagId && title.trim() && body.trim());

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden bg-surface p-0">
        <DialogHeader className="border-b border-border px-6 py-4">
          <DialogTitle className="text-lg font-semibold">
            {isEditMode
              ? t("announcements.editor.editTitle")
              : t("announcements.editor.createTitle")}
          </DialogTitle>
        </DialogHeader>

        {/* Confirm overwrite dialog */}
        {pendingTemplateConfirm && (
          <div className="absolute inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
            <div className="mx-4 rounded-lg border border-border bg-surface p-6 shadow-xl">
              <p className="mb-4 text-body text-foreground">
                {t("announcements.editor.templateAppliedConfirm")}
              </p>
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPendingTemplateConfirm(false)}
                >
                  {t("common.actions.cancel")}
                </Button>
                <Button size="sm" onClick={handleConfirmApplyTemplate}>
                  {t("announcements.editor.applyTemplate")}
                </Button>
              </div>
            </div>
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {/* Tag select */}
          <div className="mb-5">
            <label className="mb-1.5 block text-caption text-muted-foreground">
              {t("announcements.editor.tagLabel")}
            </label>
            <Select value={tagId} onValueChange={handleTagChange}>
              <SelectTrigger className="w-full sm:w-64">
                <SelectValue placeholder={t("announcements.editor.tagLabel")} />
              </SelectTrigger>
              <SelectContent>
                {tags.map((item) => (
                  <SelectItem key={item.id} value={item.id}>
                    {getTagDisplayName(item)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Language tabs */}
          <Tabs
            value={activeLang}
            onValueChange={(v) => setActiveLang(v as Lang)}
            className="mb-4"
          >
            <div className="flex items-center justify-between">
              <TabsList className="bg-background">
                <TabsTrigger value="ko">{t("announcements.editor.langKo")}</TabsTrigger>
                <TabsTrigger value="en">{t("announcements.editor.langEn")}</TabsTrigger>
                <TabsTrigger value="ja">{t("announcements.editor.langJa")}</TabsTrigger>
              </TabsList>

              {/* Edit / Preview toggle */}
              <div className="flex rounded-md border border-border">
                <button
                  type="button"
                  onClick={() => setActiveMode("edit")}
                  className={`px-3 py-1 text-caption transition-colors ${
                    activeMode === "edit"
                      ? "bg-primary/20 text-primary"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {t("announcements.editor.edit")}
                </button>
                <button
                  type="button"
                  onClick={() => setActiveMode("preview")}
                  className={`border-l border-border px-3 py-1 text-caption transition-colors ${
                    activeMode === "preview"
                      ? "bg-primary/20 text-primary"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {t("announcements.editor.preview")}
                </button>
              </div>
            </div>
          </Tabs>

          {activeMode === "edit" ? (
            <div className="space-y-4">
              {/* Title */}
              <div>
                <label className="mb-1.5 block text-caption text-muted-foreground">
                  {t("announcements.editor.titleLabel")}
                  {activeLang !== "ko" && (
                    <span className="ml-1 text-muted-foreground/60">
                      ({activeLang === "en" ? t("announcements.editor.langEn") : t("announcements.editor.langJa")})
                    </span>
                  )}
                </label>
                <Input
                  value={currentTitle}
                  onChange={(e) => setCurrentTitle(e.target.value)}
                  className="bg-background"
                  placeholder={activeLang !== "ko" ? title : undefined}
                />
              </div>

              {/* Body */}
              <div>
                <label className="mb-1.5 block text-caption text-muted-foreground">
                  {t("announcements.editor.bodyLabel")}
                </label>
                <textarea
                  value={currentBody}
                  onChange={(e) => setCurrentBody(e.target.value)}
                  className="min-h-[200px] w-full resize-y rounded-md border border-input bg-background px-3 py-2 font-mono text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                  placeholder={activeLang !== "ko" ? body : undefined}
                />
              </div>
            </div>
          ) : (
            /* Preview */
            <div className="rounded-lg border border-border bg-card p-4">
              <h2 className="mb-3 text-lg font-semibold text-foreground">
                {previewTitle || <span className="text-muted-foreground">(no title)</span>}
              </h2>
              {previewBody ? (
                <MarkdownContent className="text-foreground [&_blockquote]:text-foreground">
                  {previewBody}
                </MarkdownContent>
              ) : (
                <p className="text-muted-foreground">(no content)</p>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-border px-6 py-3">
          {/* Feedback message */}
          {feedback && (
            <p className="mb-2 text-center text-caption text-primary">{feedback}</p>
          )}

          <div className="flex flex-wrap items-center justify-between gap-2">
            {/* Template actions */}
            <div className="flex gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleApplyTemplate}
                disabled={!tagId}
                className="text-muted-foreground hover:text-foreground"
              >
                {t("announcements.editor.applyTemplate")}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleSaveTemplate}
                disabled={!canSave || upsertTemplate.isPending}
                className="text-muted-foreground hover:text-foreground"
              >
                {t("announcements.editor.saveTemplate")}
              </Button>
            </div>

            {/* Save / Publish */}
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleSaveDraft}
                disabled={!canSave || saving}
              >
                {t("announcements.editor.saveDraft")}
              </Button>
              <Button
                size="sm"
                onClick={handlePublish}
                disabled={!canSave || publishing}
                className="bg-primary text-primary-foreground hover:bg-primary/90"
              >
                {t("announcements.editor.publish")}
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
