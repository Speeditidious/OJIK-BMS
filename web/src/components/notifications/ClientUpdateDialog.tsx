"use client";

import { Download } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import { MarkdownContent } from "@/components/common/MarkdownContent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { NotificationItem } from "@/types";

interface ClientUpdateDialogProps {
  item: NotificationItem | null;
  onClose: () => void;
}

export function ClientUpdateDialog({ item, onClose }: ClientUpdateDialogProps) {
  const { t, i18n } = useTranslation();
  const router = useRouter();

  const getBody = (): string | null => {
    if (!item) return null;
    const meta = item.metadata ?? {};
    if (i18n.language === "en" && typeof meta.body_en === "string") return meta.body_en;
    if (i18n.language === "ja" && typeof meta.body_ja === "string") return meta.body_ja;
    return item.body;
  };

  const handleGoToDownload = () => {
    onClose();
    router.push("/download");
  };

  return (
    <Dialog open={item !== null} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15">
              <Download className="h-4 w-4 text-primary" />
            </div>
            <DialogTitle className="text-left text-body font-semibold leading-snug">
              {item?.title}
            </DialogTitle>
          </div>
        </DialogHeader>

        {getBody() && (
          <div className="max-h-72 overflow-y-auto py-1">
            <MarkdownContent className="text-label text-muted-foreground">
              {getBody()!}
            </MarkdownContent>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={handleGoToDownload}>
            <Download className="mr-1.5 h-4 w-4" />
            {t("notifications.clientUpdateDialog.goToDownload")}
          </Button>
          <Button onClick={onClose}>
            {t("notifications.clientUpdateDialog.confirm")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
