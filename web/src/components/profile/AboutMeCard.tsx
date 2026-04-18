"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface AboutMeCardProps {
  bio: string | null;
  isOwner: boolean;
}

export function AboutMeCard({ bio, isOwner }: AboutMeCardProps) {
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
              아직 자기소개가 작성되지 않았습니다.
            </p>
            {isOwner && (
              <Link href="/settings" className="inline-flex text-label text-primary hover:underline">
                설정에서 자기소개 편집
              </Link>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
