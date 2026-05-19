"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { AlertTriangle, CheckCircle2, ExternalLink, Info, Loader2, Star } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { DifficultyTable, ImportTableResponse, TableImportQuota } from "@/types";

interface ImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported?: (table: DifficultyTable) => void;
  onOpenTable?: (tableId: string) => void;
}

type DialogStep =
  | { type: "idle" }
  | { type: "loading" }
  | { type: "created"; result: ImportTableResponse }
  | { type: "duplicate"; result: ImportTableResponse }
  | { type: "error"; message: string }
  | { type: "quota"; quota: TableImportQuota };

function QuotaBar({ quota }: { quota: TableImportQuota }) {
  const { t } = useTranslation();
  const pct = (quota.created_remaining / quota.created_limit) * 100;
  const isLow = quota.created_remaining <= 1;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-caption text-muted-foreground">
          {t("tables.importDialog.quotaLabel")}
        </span>
        <span className={cn("text-caption font-semibold", isLow ? "text-warning" : "text-foreground")}>
          {quota.created_remaining} / {quota.created_limit}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            isLow ? "bg-warning" : "bg-primary",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function Callout({
  variant,
  icon: Icon,
  children,
}: {
  variant: "success" | "info" | "error" | "warning";
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  const variantStyles = {
    success: "border-primary/30 bg-primary/10 text-primary dark:bg-primary/15",
    info: "border-accent/30 bg-accent/10 text-accent dark:bg-accent/15",
    error: "border-destructive/30 bg-destructive/10 text-destructive dark:bg-destructive/15",
    warning: "border-warning/30 bg-warning/10 text-warning dark:bg-warning/15",
  };

  return (
    <div className={cn("flex items-start gap-3 rounded-lg border p-4", variantStyles[variant])}>
      <Icon className="mt-0.5 h-5 w-5 shrink-0" />
      <div className="min-w-0 flex-1 text-body">{children}</div>
    </div>
  );
}

export function ImportDialog({ open, onOpenChange, onImported, onOpenTable }: ImportDialogProps) {
  const { t } = useTranslation();
  const [url, setUrl] = useState("");
  const [step, setStep] = useState<DialogStep>({ type: "idle" });
  const [quota, setQuota] = useState<TableImportQuota | null>(null);
  const queryClient = useQueryClient();

  const importMutation = useMutation({
    mutationFn: (url: string) => api.post<ImportTableResponse>("/tables/import", { url }),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["tables"] });
      queryClient.invalidateQueries({ queryKey: ["tables", "favorites"] });
      if (response.quota) setQuota(response.quota);
      setStep(
        response.outcome === "duplicate"
          ? { type: "duplicate", result: response }
          : { type: "created", result: response },
      );
      onImported?.(response.table);
    },
    onError: (err: { status?: number; message: string }) => {
      if (err.status === 429) {
        // Fetch fresh quota to show reset time
        api.get<TableImportQuota>("/tables/import/quota")
          .then((q) => setStep({ type: "quota", quota: q }))
          .catch(() => setStep({ type: "error", message: err.message }));
      } else {
        setStep({ type: "error", message: err.message });
      }
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setStep({ type: "loading" });
    importMutation.mutate(url.trim());
  };

  const handleOpenChange = (nextOpen: boolean) => {
    onOpenChange(nextOpen);
    if (nextOpen) {
      setStep({ type: "idle" });
      setUrl("");
      api.get<TableImportQuota>("/tables/import/quota").then(setQuota).catch(() => undefined);
    }
  };

  const handleClose = () => handleOpenChange(false);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("tables.importDialog.title")}</DialogTitle>
        </DialogHeader>

        {/* ── IDLE / ERROR: URL input form ── */}
        {(step.type === "idle" || step.type === "error") && (
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Help text */}
            <div className="flex items-start gap-2 rounded-lg bg-muted/60 px-3 py-2.5">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <p className="text-label text-muted-foreground">
                {t("tables.importDialog.helpText")}
              </p>
            </div>

            <Input
              placeholder="https://example.com/table.html"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              autoFocus
            />

            {/* Error state */}
            {step.type === "error" && (
              <Callout variant="error" icon={AlertTriangle}>
                {step.message}
              </Callout>
            )}

            {/* Quota bar */}
            {quota && <QuotaBar quota={quota} />}

            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={handleClose}>
                {t("tables.importDialog.cancel")}
              </Button>
              <Button type="submit" disabled={!url.trim()}>
                {t("tables.importDialog.submit")}
              </Button>
            </div>
          </form>
        )}

        {/* ── LOADING ── */}
        {step.type === "loading" && (
          <div className="flex flex-col items-center gap-4 py-8">
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
            <p className="text-body text-muted-foreground">{t("tables.importDialog.submitting")}</p>
          </div>
        )}

        {/* ── CREATED: success ── */}
        {step.type === "created" && (
          <div className="space-y-4">
            <Callout variant="success" icon={CheckCircle2}>
              <p className="font-semibold">{t("tables.importDialog.created")}</p>
              <p className="mt-0.5 text-label opacity-80">{step.result.table.name}</p>
            </Callout>
            {step.result.quota && <QuotaBar quota={step.result.quota} />}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={handleClose}>
                {t("tables.importDialog.close")}
              </Button>
              {onOpenTable && (
                <Button
                  onClick={() => {
                    onOpenTable(step.result.table.id);
                    handleClose();
                  }}
                >
                  <ExternalLink className="mr-1.5 h-4 w-4" />
                  {t("tables.importDialog.openTable")}
                </Button>
              )}
            </div>
          </div>
        )}

        {/* ── DUPLICATE: already exists ── */}
        {step.type === "duplicate" && (
          <div className="space-y-4">
            <Callout variant="info" icon={Star}>
              <p className="font-semibold">{t("tables.importDialog.duplicate")}</p>
              <p className="mt-0.5 text-label opacity-80">{step.result.message}</p>
            </Callout>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={handleClose}>
                {t("tables.importDialog.close")}
              </Button>
              {onOpenTable && (
                <Button
                  variant="secondary"
                  onClick={() => {
                    onOpenTable(step.result.table.id);
                    handleClose();
                  }}
                >
                  <ExternalLink className="mr-1.5 h-4 w-4" />
                  {t("tables.importDialog.openTable")}
                </Button>
              )}
            </div>
          </div>
        )}

        {/* ── QUOTA EXCEEDED ── */}
        {step.type === "quota" && (
          <div className="space-y-4">
            <Callout variant="warning" icon={AlertTriangle}>
              <p className="font-semibold">{t("tables.importDialog.quotaBlocked")}</p>
              {step.quota.created_reset_at && (
                <p className="mt-1 text-label opacity-80">
                  {t("tables.importDialog.quotaResetAt", {
                    time: new Date(step.quota.created_reset_at).toLocaleTimeString(undefined, {
                      hour: "2-digit",
                      minute: "2-digit",
                    }),
                  })}
                </p>
              )}
            </Callout>
            <div className="flex justify-end">
              <Button variant="outline" onClick={handleClose}>
                {t("tables.importDialog.close")}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
