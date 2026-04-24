"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/stores/auth";

export function LoginButton() {
  const { user, isInitialized } = useAuthStore();
  const router = useRouter();

  function handleClick(e: React.MouseEvent) {
    if (isInitialized && user) {
      e.preventDefault();
      router.push(`/users/${user.id}/dashboard`);
    }
  }

  return (
    <Link href="/login" onClick={handleClick}>
      <Button
        size="lg"
        className="gap-2 hover:opacity-90 transition-opacity"
        style={{ backgroundColor: "#5865F2", borderColor: "#5865F2", color: "white" }}
      >
        <Image
          src="/discord_white_icon.png"
          alt="Discord"
          width={256}
          height={194}
          style={{ width: 20, height: "auto" }}
        />
        Discord로 시작하기
      </Button>
    </Link>
  );
}
