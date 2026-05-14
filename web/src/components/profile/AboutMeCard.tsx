"use client";

import Link from "next/link";
import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface AboutMeCardProps {
  bio: string | null;
  isOwner: boolean;
}

export function AboutMeCard({ bio, isOwner }: AboutMeCardProps) {
  const { t } = useTranslation();

  return (
    <Card>
      <CardHeader>
        <CardTitle>About Me</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {bio ? (
          <p className="whitespace-pre-line text-body text-foreground">{bio}</p>
        ) : (
          <>
            <p className="text-body text-muted-foreground">
              {t("profile.about.empty")}
            </p>
            {isOwner && (
              <Link href="/settings" className="inline-flex text-label text-primary hover:underline">
                {t("profile.about.editInSettings")}
              </Link>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
