"use client";

import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";

export type DayStatSheetExportMode = "single" | "sections" | "height";
export type DayStatSheetHeightSplitMode = "component" | "exact";

export interface DayStatSheetExportOptions {
  mode: DayStatSheetExportMode;
  maxHeight: number;
  heightSplitMode: DayStatSheetHeightSplitMode;
}

export interface DayStatSheetPreviewImage {
  dataUrl: string;
  filename: string;
  label: string;
}

interface DayStatSheetPreviewDialogProps {
  open: boolean;
  images: DayStatSheetPreviewImage[];
  isGenerating: boolean;
  options: DayStatSheetExportOptions;
  onOptionsChange: (options: DayStatSheetExportOptions) => void;
  onClose: () => void;
}

export function DayStatSheetPreviewDialog({
  open,
  images,
  isGenerating,
  options,
  onOptionsChange,
  onClose,
}: DayStatSheetPreviewDialogProps) {
  const { t } = useTranslation();
  const previewScrollRef = useRef<HTMLDivElement>(null);
  const [heightInput, setHeightInput] = useState(String(options.maxHeight));
  const [pageIndex, setPageIndex] = useState(0);
  const pageCount = images.length;
  const currentPageIndex = pageCount > 0 ? Math.min(pageIndex, pageCount - 1) : 0;
  const currentImage = images[currentPageIndex] ?? null;
  const pageText = pageCount > 1 ? `${currentPageIndex + 1}/${pageCount}` : null;

  function handleSave() {
    for (const image of images) {
      const a = document.createElement("a");
      a.href = image.dataUrl;
      a.download = image.filename;
      a.click();
    }
  }

  function setMode(mode: DayStatSheetExportMode) {
    if (options.mode === mode) return;
    setPageIndex(0);
    onOptionsChange({ ...options, mode });
  }

  function setHeightSplitMode(heightSplitMode: DayStatSheetHeightSplitMode) {
    if (options.heightSplitMode === heightSplitMode) return;
    setPageIndex(0);
    onOptionsChange({ ...options, heightSplitMode });
  }

  function commitMaxHeight() {
    const parsed = Number.parseInt(heightInput, 10);
    const maxHeight = Number.isFinite(parsed) ? Math.max(500, Math.min(12000, parsed)) : 1960;
    setHeightInput(String(maxHeight));
    if (options.maxHeight === maxHeight) return;
    setPageIndex(0);
    onOptionsChange({
      ...options,
      maxHeight,
    });
  }

  function goToPage(nextPageIndex: number) {
    setPageIndex(Math.max(0, Math.min(pageCount - 1, nextPageIndex)));
    previewScrollRef.current?.scrollTo({ top: 0 });
  }

  const modeOptions: Array<{ value: DayStatSheetExportMode; label: string }> = [
    { value: "single", label: t("dashboard.daySheet.exportSingle") },
    { value: "sections", label: t("dashboard.daySheet.exportSections") },
    { value: "height", label: t("dashboard.daySheet.exportByHeight") },
  ];

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-3xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span>{t("dashboard.scoreUpdates.imagePreviewTitle")}</span>
            {pageText && <span className="text-body font-medium text-muted-foreground">{pageText}</span>}
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-3 rounded-xl border border-border/40 bg-muted/20 p-3">
          <div className="space-y-2">
            <p className="text-label font-semibold uppercase tracking-wide text-muted-foreground">
              {t("dashboard.daySheet.exportLayout")}
            </p>
            <div className="grid grid-cols-3 gap-1.5">
              {modeOptions.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => setMode(item.value)}
                  className={cn(
                    "rounded-full border px-3 py-1.5 text-label font-medium transition-colors",
                    options.mode === item.value
                      ? "border-primary/60 bg-primary/10 text-primary"
                      : "border-border/50 bg-background text-muted-foreground hover:border-primary/40 hover:text-foreground",
                  )}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          {options.mode === "height" && (
            <div className="grid gap-3 border-t border-border/40 pt-3 md:grid-cols-[150px_1fr]">
              <label className="space-y-1">
                <span className="text-label font-semibold tracking-wide text-muted-foreground">
                  {t("dashboard.daySheet.exportMaxHeight")}
                </span>
                <Input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  value={heightInput}
                  onChange={(event) => setHeightInput(event.target.value)}
                  onBlur={commitMaxHeight}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.currentTarget.blur();
                    }
                  }}
                  className="h-9"
                />
              </label>
              <div className="space-y-1">
                <p className="text-label font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("dashboard.daySheet.exportSplitRule")}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {(["component", "exact"] as const).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setHeightSplitMode(mode)}
                      className={cn(
                        "rounded-full border px-3 py-1.5 text-label font-medium transition-colors",
                        options.heightSplitMode === mode
                          ? "border-primary/60 bg-primary/10 text-primary"
                          : "border-border/50 bg-background text-muted-foreground hover:border-primary/40 hover:text-foreground",
                      )}
                    >
                      {t(
                        mode === "component"
                          ? "dashboard.daySheet.exportPreserveComponents"
                          : "dashboard.daySheet.exportExactHeight",
                      )}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <div
          ref={previewScrollRef}
          className="flex-1 overflow-auto min-h-0 rounded-md border border-border/40 bg-muted/10 p-2"
        >
          {currentImage ? (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={currentImage.dataUrl} alt={currentImage.label} className="w-full rounded-md" />
            </>
          ) : (
            <div className="flex h-40 items-center justify-center text-muted-foreground text-body">
              {isGenerating ? (
                <Loader2 className="h-7 w-7 animate-spin" aria-label={t("common.status.loading")} />
              ) : (
                t("dashboard.scoreUpdates.imageSaveFailed")
              )}
            </div>
          )}
        </div>
        {pageCount > 1 && (
          <div className="flex items-center justify-center gap-3">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => goToPage(currentPageIndex - 1)}
              disabled={currentPageIndex === 0}
              aria-label={t("common.actions.prev")}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="min-w-8 text-center text-label font-semibold text-muted-foreground tabular-nums">
              {currentPageIndex + 1}
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => goToPage(currentPageIndex + 1)}
              disabled={currentPageIndex >= pageCount - 1}
              aria-label={t("common.actions.next")}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}
        <DialogFooter className="flex gap-2">
          <Button variant="outline" onClick={onClose}>{t("common.actions.close")}</Button>
          <Button onClick={handleSave} disabled={images.length === 0 || isGenerating}>
            {t("dashboard.scoreUpdates.saveImage")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
