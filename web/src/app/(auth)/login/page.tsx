"use client";

import { useSearchParams } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";
import { AlertCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function LoginContent() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const error = searchParams.get("error");

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <Image src="/ojikbms_logo.png" alt="OJIK BMS" width={64} height={64} />
          </div>
          <CardTitle className="text-2xl">{t("auth.login.title")}</CardTitle>
          <CardDescription>
            {t("auth.login.description")}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-3 py-2 text-body text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          <a href={`${API_URL}/auth/discord/login`}>
            <Button className="w-full gap-3" size="lg">
              <Image
                src="/discord_white_icon.png"
                alt="Discord"
                width={256}
                height={194}
                style={{ width: 20, height: "auto" }}
              />
              {t("auth.login.discordLogin")}
            </Button>
          </a>
          <p className="text-center text-body text-muted-foreground">
            {t("auth.login.termsPrefix")}{" "}
            <Link href="/rules" className="underline underline-offset-4 hover:text-primary">
              {t("auth.login.termsLink")}
            </Link>
            {t("auth.login.termsSuffix")}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-background">
          <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
        </div>
      }
    >
      <LoginContent />
    </Suspense>
  );
}
