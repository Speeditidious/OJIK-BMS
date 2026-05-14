"use client";

import Link from "next/link";
import { useTranslation } from "react-i18next";
import { Settings } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ProfileActionBarProps {
  isOwner: boolean;
}

export function ProfileActionBar({ isOwner }: ProfileActionBarProps) {
  const { t } = useTranslation();

  if (!isOwner) {
    return null;
  }

  return (
    <div className="flex items-center justify-end">
      <Button asChild variant="outline" size="sm" className="gap-2">
        <Link href="/settings">
          <Settings className="h-4 w-4" />
          {t("profile.actions.settings")}
        </Link>
      </Button>
    </div>
  );
}
