"use client";

import Image from "next/image";
import Link from "next/link";
import { BookOpen, LayoutDashboard } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/stores/auth";

export function LoginButton() {
  const { t } = useTranslation();
  const { user, isInitialized } = useAuthStore();

  if (isInitialized && user) {
    return (
      <Link href={`/users/${user.id}/dashboard`}>
        <Button size="lg" className="gap-2 px-10 py-6 text-lg hover:opacity-90 transition-opacity">
          <LayoutDashboard className="h-6 w-6" />
          {t("home.hero.dashboardAction")}
        </Button>
      </Link>
    );
  }

  return (
    <>
      <Link href="/login">
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
          {t("home.hero.primaryAction")}
        </Button>
      </Link>
      <Button
        size="lg"
        variant="outline"
        className="gap-2 border-border bg-background/85"
        onClick={() => {
          document.getElementById("guide")?.scrollIntoView({ behavior: "smooth" });
        }}
      >
        <BookOpen className="h-5 w-5" />
        {t("home.hero.secondaryAction")}
      </Button>
    </>
  );
}
