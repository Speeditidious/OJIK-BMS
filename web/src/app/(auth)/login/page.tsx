"use client";

import { useSearchParams } from "next/navigation";
import Image from "next/image";
import { Suspense } from "react";
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function LoginContent() {
  const searchParams = useSearchParams();
  const error = searchParams.get("error");

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <Image src="/ojikbms_logo.png" alt="OJIK BMS" width={64} height={64} />
          </div>
          <CardTitle className="text-2xl">OJIK BMS에 오신 것을 환영합니다</CardTitle>
          <CardDescription>
            Discord 계정으로 로그인하여 BMS 플레이 데이터를 관리하세요
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          <a href={`${API_URL}/auth/discord/login`}>
            <Button className="w-full gap-3" size="lg">
              <Image src="/discord_white_icon.png" alt="Discord" width={20} height={20} />
              Discord로 로그인
            </Button>
          </a>
          <p className="text-center text-sm text-muted-foreground">
            로그인하면{" "}
            <a href="#" className="underline underline-offset-4 hover:text-primary">
              이용약관
            </a>
            에 동의한 것으로 간주됩니다.
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
