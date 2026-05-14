"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { DifficultyTable } from "@/types";

interface ImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported?: (table: DifficultyTable) => void;
}

export function ImportDialog({ open, onOpenChange, onImported }: ImportDialogProps) {
  const { t } = useTranslation();
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const importMutation = useMutation({
    mutationFn: (url: string) =>
      api.post<DifficultyTable>("/tables/import", { url }),
    onSuccess: (table) => {
      queryClient.invalidateQueries({ queryKey: ["tables"] });
      queryClient.invalidateQueries({ queryKey: ["tables", "favorites"] });
      setUrl("");
      setError(null);
      onOpenChange(false);
      onImported?.(table);
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!url.trim()) return;
    importMutation.mutate(url.trim());
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("tables.importDialog.title")}</DialogTitle>
          <DialogDescription>
            {t("tables.importDialog.description")}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            placeholder="https://example.com/table.html"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={importMutation.isPending}
          />
          {error && (
            <p className="text-body text-destructive">{error}</p>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={importMutation.isPending}
            >
              {t("tables.importDialog.cancel")}
            </Button>
            <Button type="submit" disabled={!url.trim() || importMutation.isPending}>
              {importMutation.isPending ? t("tables.importDialog.submitting") : t("tables.importDialog.submit")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
