"use client";

import { useState } from "react";
import { Download, ExternalLink, Terminal, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useGitHubRelease } from "@/hooks/use-github-release";
import { Navbar } from "@/components/layout/navbar";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export default function DownloadPage() {
  const { data: release, isLoading, isError } = useGitHubRelease();
  const [cliOpen, setCliOpen] = useState(false);

  const hasRelease = release && release.version;

  return (
    <>
    <Navbar />
    <div className="container max-w-2xl py-12 space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold">OJIK BMS 클라이언트 다운로드</h1>
        <p className="text-muted-foreground">
          로컬에 있는 BMS 데이터베이스들을 스캔하고 서버에 동기화하는 도구입니다.
        </p>
      </div>

      {/* Release card */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-3">
            {isLoading ? (
              <Skeleton className="h-6 w-32" />
            ) : hasRelease ? (
              <>
                <span>최신 버전</span>
                <Badge variant="secondary">{release.version}</Badge>
                <span className="text-sm font-normal text-muted-foreground ml-auto">
                  {formatDate(release.publishedAt)}
                </span>
              </>
            ) : (
              <span>다운로드</span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? (
            <div className="flex gap-3">
              <Skeleton className="h-10 w-48" />
              <Skeleton className="h-10 w-36" />
            </div>
          ) : hasRelease ? (
            <div className="flex flex-wrap gap-3">
              {release.exeDownloadUrl ? (
                <Button asChild>
                  <a href={release.exeDownloadUrl} download>
                    <Download className="h-4 w-4 mr-2" />
                    Windows exe 다운로드
                  </a>
                </Button>
              ) : (
                <Button disabled>
                  <Download className="h-4 w-4 mr-2" />
                  Windows exe (준비 중)
                </Button>
              )}
              <Button variant="outline" asChild>
                <a href={release.releasePageUrl} target="_blank" rel="noopener noreferrer">
                  GitHub 릴리즈 페이지
                  <ExternalLink className="h-4 w-4 ml-2" />
                </a>
              </Button>
            </div>
          ) : isError || !process.env.NEXT_PUBLIC_GITHUB_REPO ? (
            <div className="space-y-3">
              <p className="text-muted-foreground text-sm">
                릴리즈 정보를 불러올 수 없습니다. 잠시 후 다시 시도해 주세요.
              </p>
              {process.env.NEXT_PUBLIC_GITHUB_REPO && (
                <Button variant="outline" asChild>
                  <a
                    href={`https://github.com/${process.env.NEXT_PUBLIC_GITHUB_REPO}/releases`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    GitHub에서 직접 다운로드
                    <ExternalLink className="h-4 w-4 ml-2" />
                  </a>
                </Button>
              )}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">
              아직 배포된 릴리즈가 없습니다. 곧 출시될 예정입니다.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Getting started */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>시작하기</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="space-y-4">
            <li className="flex gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-sm font-semibold">
                1
              </span>
              <div>
                <p className="font-medium">exe 다운로드 후 실행</p>
                <p className="text-sm text-muted-foreground">추가 설치 없이 바로 실행됩니다.</p>
              </div>
            </li>
            <li className="flex gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-sm font-semibold">
                2
              </span>
              <div>
                <p className="font-medium">Discord 로그인</p>
                <p className="text-sm text-muted-foreground">
                  OJIK BMS 계정과 동일한 Discord 계정으로 인증합니다.
                </p>
              </div>
            </li>
            <li className="flex gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-sm font-semibold">
                3
              </span>
              <div>
                <p className="font-medium">경로 설정 후 동기화</p>
                <p className="text-sm text-muted-foreground">
                  각 구동기의 데이터베이스 경로를 지정하면 자동으로 스캔 · 동기화됩니다.
                </p>
              </div>
            </li>
          </ol>
        </CardContent>
      </Card>
    </div>
    </>
  );
}
