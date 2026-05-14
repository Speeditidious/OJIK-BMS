"use client";

import { Download, ExternalLink } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useGitHubRelease } from "@/hooks/use-github-release";
import { Navbar } from "@/components/layout/navbar";

type DownloadStep = {
  title: string;
  description: string;
};

function formatDate(iso: string, language: string) {
  const locale = language.startsWith("ja") ? "ja-JP" : language.startsWith("en") ? "en-US" : "ko-KR";

  return new Date(iso).toLocaleDateString(locale, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export default function DownloadPage() {
  const { t, i18n } = useTranslation();
  const { data: release, isLoading, isError } = useGitHubRelease();
  const steps = t("download.steps", { returnObjects: true }) as DownloadStep[];

  const hasRelease = release && release.version;

  return (
    <>
    <Navbar />
    <div className="container max-w-2xl py-12 space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold">{t("download.title")}</h1>
        <p className="text-muted-foreground">
          {t("download.description")}
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
                <span>{t("download.latestVersion")}</span>
                <Badge variant="secondary">{release.version}</Badge>
                <span className="text-body font-normal text-muted-foreground ml-auto">
                  {formatDate(release.publishedAt, i18n.language)}
                </span>
              </>
            ) : (
              <span>{t("download.download")}</span>
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
                    {t("download.windowsDownload")}
                  </a>
                </Button>
              ) : (
                <Button disabled>
                  <Download className="h-4 w-4 mr-2" />
                  {t("download.windowsPreparing")}
                </Button>
              )}
              <Button variant="outline" asChild>
                <a href={release.releasePageUrl} target="_blank" rel="noopener noreferrer">
                  {t("download.githubRelease")}
                  <ExternalLink className="h-4 w-4 ml-2" />
                </a>
              </Button>
            </div>
          ) : isError || !process.env.NEXT_PUBLIC_GITHUB_REPO ? (
            <div className="space-y-3">
              <p className="text-muted-foreground text-body">
                {t("download.loadFailed")}
              </p>
              {process.env.NEXT_PUBLIC_GITHUB_REPO && (
                <Button variant="outline" asChild>
                  <a
                    href={`https://github.com/${process.env.NEXT_PUBLIC_GITHUB_REPO}/releases`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {t("download.directDownload")}
                    <ExternalLink className="h-4 w-4 ml-2" />
                  </a>
                </Button>
              )}
            </div>
          ) : (
            <p className="text-muted-foreground text-body">
              {t("download.noRelease")}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Getting started */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>{t("download.gettingStarted")}</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="space-y-4">
            {steps.map((step, index) => (
              <li key={step.title} className="flex gap-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-body font-semibold">
                  {index + 1}
                </span>
                <div>
                  <p className="font-medium">{step.title}</p>
                  <p className="text-body text-muted-foreground">{step.description}</p>
                </div>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </div>
    </>
  );
}
