"use client";

import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { MarkdownContent } from "@/components/common/MarkdownContent";

export interface MarkdownEditorProps {
  initialBody: string;
  onSave: (body: string) => Promise<void>;
  onCancel: () => void;
  isSaving: boolean;
  placeholder?: string;
  maxLength?: number;
  /** When true, @user and #issue autocomplete is enabled. Default: false. */
  enableMentions?: boolean;
  /** Render mention autocomplete UI — only used when enableMentions is true. */
  renderMentionDropdown?: (
    body: string,
    textarea: HTMLTextAreaElement | null,
    setBody: (v: string) => void,
  ) => React.ReactNode;
  /** When true, save is enabled even if body is unchanged (e.g. only a title changed). */
  hasExternalChanges?: boolean;
  /**
   * When true, an empty body can be saved (the caller decides what an empty
   * save means — e.g. deleting the record). Default: false (empty blocks save).
   */
  allowEmpty?: boolean;
}

export function MarkdownEditor({
  initialBody,
  onSave,
  onCancel,
  isSaving,
  placeholder,
  maxLength,
  enableMentions = false,
  renderMentionDropdown,
  hasExternalChanges = false,
  allowEmpty = false,
}: MarkdownEditorProps) {
  const { t } = useTranslation();
  const [body, setBody] = useState(initialBody);
  const [activeTab, setActiveTab] = useState<"edit" | "preview">("edit");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [textareaEl, setTextareaEl] = useState<HTMLTextAreaElement | null>(null);
  const textareaCallbackRef = useCallback((el: HTMLTextAreaElement | null) => setTextareaEl(el), []);

  const hasChanged = body.trim() !== initialBody.trim() || hasExternalChanges;
  const overLimit = maxLength != null && body.length > maxLength;

  function handleCancelClick() {
    if (hasChanged) {
      setConfirmOpen(true);
    } else {
      onCancel();
    }
  }

  return (
    <>
      <div className="flex-1 rounded-lg border overflow-hidden">
        <div className="flex items-center border-b bg-muted/30">
          <div className="flex flex-1">
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
                {t(tab === "edit" ? "common.editor.write" : "common.editor.preview")}
              </button>
            ))}
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 mr-2 text-muted-foreground hover:text-foreground shrink-0"
            onClick={handleCancelClick}
            aria-label={t("common.editor.cancel")}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="relative">
          {activeTab === "edit" ? (
            <Textarea
              ref={textareaCallbackRef}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder={placeholder ?? t("common.editor.placeholder")}
              className="min-h-24 rounded-none border-0 resize-none focus-visible:ring-0"
              rows={4}
            />
          ) : (
            <div className="min-h-24 p-4">
              {body ? (
                <MarkdownContent>{body}</MarkdownContent>
              ) : (
                <p className="text-muted-foreground text-label italic">
                  {placeholder ?? t("common.editor.placeholder")}
                </p>
              )}
            </div>
          )}

          {enableMentions && renderMentionDropdown?.(body, textareaEl, setBody)}
        </div>

        <div className="flex items-center justify-between p-2 border-t bg-muted/30">
          {maxLength != null ? (
            <span className={["text-label", overLimit ? "text-destructive" : "text-muted-foreground"].join(" ")}>
              {body.length} / {maxLength}
            </span>
          ) : (
            <span />
          )}
          <Button
            size="sm"
            disabled={(!allowEmpty && !body.trim()) || !hasChanged || isSaving || overLimit}
            onClick={async () => {
              if ((!allowEmpty && !body.trim()) || !hasChanged || overLimit) return;
              await onSave(body.trim());
            }}
          >
            {isSaving ? t("common.editor.saving") : t("common.editor.save")}
          </Button>
        </div>
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("common.editor.cancelConfirmTitle")}</DialogTitle>
            <DialogDescription>{t("common.editor.cancelConfirmBody")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              {t("common.actions.cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setConfirmOpen(false);
                onCancel();
              }}
            >
              {t("common.actions.confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
