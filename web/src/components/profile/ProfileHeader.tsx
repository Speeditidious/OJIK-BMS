"use client";

import Image from "next/image";
import Link from "next/link";
import { Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { resolveAvatarUrl } from "@/lib/avatar";

interface ProfileHeaderProps {
  username: string;
  avatarUrl?: string | null;
  bio?: string | null;
  isOwner: boolean;
}

export function ProfileHeader({ username, avatarUrl, bio, isOwner }: ProfileHeaderProps) {
  return (
    <div className="flex items-start gap-4 mb-8">
      {avatarUrl ? (
        <Image
          src={resolveAvatarUrl(avatarUrl)}
          alt={username}
          width={64}
          height={64}
          className="rounded-full object-cover ring-2 ring-primary/30"
        />
      ) : (
        <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center text-2xl font-bold text-primary ring-2 ring-primary/30">
          {username.charAt(0).toUpperCase()}
        </div>
      )}

      <div className="flex-1">
        <h1 className="text-2xl font-bold">{username}</h1>
        {bio ? (
          <p className="text-body text-muted-foreground mt-1 whitespace-pre-line">{bio}</p>
        ) : (
          <p className="text-label text-muted-foreground mt-0.5">
            {isOwner ? "내 게임 프로필" : `${username}의 게임 프로필`}
          </p>
        )}
      </div>

      {isOwner && (
        <Link href="/settings">
          <Button variant="outline" size="sm" className="gap-2">
            <Settings className="h-4 w-4" />
            설정
          </Button>
        </Link>
      )}
    </div>
  );
}
