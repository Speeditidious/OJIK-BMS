"use client";

import { Download, ExternalLink } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useGitHubRelease } from "@/hooks/use-github-release";
import { Navbar } from "@/components/layout/navbar";

function WindowsIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M0 3.5 L10.5 2.1 L10.5 11.5 L0 11.5 Z M11.5 1.85 L24 0 L24 11.5 L11.5 11.5 Z M0 12.5 L10.5 12.5 L10.5 21.9 L0 20.5 Z M11.5 12.5 L24 12.5 L24 24 L11.5 22.15 Z" />
    </svg>
  );
}

function LinuxIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2C9.5 2 7.5 4 7.5 6.5C7.5 8.2 8.4 9.7 9.7 10.5C8.5 11.2 7 12.8 6.5 14.5C5.8 14.3 5 14.5 4.5 15.2C4 15.9 4.1 16.8 4.7 17.2C4.3 17.7 4.2 18.4 4.6 19C5 19.6 5.8 19.8 6.5 19.5C7 20.4 8 21 9.2 21C9.7 21 10.1 20.9 10.5 20.6C11 21.5 12 22 13 22C14 22 15 21.5 15.5 20.6C15.9 20.9 16.3 21 16.8 21C18 21 19 20.4 19.5 19.5C20.2 19.8 21 19.6 21.4 19C21.8 18.4 21.7 17.7 21.3 17.2C21.9 16.8 22 15.9 21.5 15.2C21 14.5 20.2 14.3 19.5 14.5C19 12.8 17.5 11.2 16.3 10.5C17.6 9.7 18.5 8.2 18.5 6.5C18.5 4 16.5 2 14 2C13.3 2 12.6 2.2 12 2.5C11.4 2.2 10.7 2 12 2ZM12 3.5C13.5 3.5 14.8 4 15.7 5C16.5 5.8 17 6.8 17 8C17 9.7 16 11.1 14.7 11.7C14.2 11.2 13.5 11 12.7 11H11.3C10.5 11 9.8 11.2 9.3 11.7C8 11.1 7 9.7 7 8C7 5.5 9.2 3.5 12 3.5ZM10.5 6C10 6 9.5 6.5 9.5 7C9.5 7.5 10 8 10.5 8C11 8 11.5 7.5 11.5 7C11.5 6.5 11 6 10.5 6ZM13.5 6C13 6 12.5 6.5 12.5 7C12.5 7.5 13 8 13.5 8C14 8 14.5 7.5 14.5 7C14.5 6.5 14 6 13.5 6ZM11 12.5H13C15.5 12.5 17.5 14.3 17.5 17V18C17.5 19.1 16.6 20 15.5 20C15 20 14.5 19.8 14.2 19.4C13.8 19.8 13.4 20 12.9 20H11.1C10.6 20 10.2 19.8 9.8 19.4C9.5 19.8 9 20 8.5 20C7.4 20 6.5 19.1 6.5 18V17C6.5 14.3 8.5 12.5 11 12.5Z" />
    </svg>
  );
}

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
              {release.downloads?.length ? (
                release.downloads.map((item) => {
                  const isWindows = item.targetOs === "windows";
                  const isLinux = item.targetOs === "linux";
                  const OsIcon = isWindows ? WindowsIcon : isLinux ? LinuxIcon : Download;
                  const label = isWindows
                    ? t("download.windowsDownload", { version: item.version })
                    : isLinux
                    ? t("download.linuxDownload", { version: item.version })
                    : item.label;
                  return (
                    <Button key={item.targetOs} asChild>
                      <a href={item.downloadUrl} download>
                        <OsIcon className="h-4 w-4 mr-2" />
                        {label}
                      </a>
                    </Button>
                  );
                })
              ) : release.exeDownloadUrl ? (
                  <Button asChild>
                    <a href={release.exeDownloadUrl} download>
                      <WindowsIcon className="h-4 w-4 mr-2" />
                      {t("download.windowsDownload", { version: release.version })}
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
