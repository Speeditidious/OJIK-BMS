"use client";

import Link from "next/link";
import Image from "next/image";
import { Music2, BarChart3, CalendarClock, Bot, CircleDot, Download, Megaphone, MessageSquare, Pin, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { GuideSection } from "@/components/home/GuideSection";
import { Navbar } from "@/components/layout/navbar";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { LoginButton } from "@/components/home/LoginButton";
import { AnnouncementCard } from "@/components/announcements/AnnouncementCard";
import { IssueStatusBadge } from "@/components/issues/IssueStatusBadge";
import { useAnnouncements } from "@/hooks/use-announcements";
import { usePinnedIssues } from "@/hooks/use-issues";
import { resolveTagBadgeStyle } from "@/lib/tag-color";
import { timeAgo } from "@/lib/time";
import type { Issue } from "@/types";

const featureIcons = [BarChart3, CalendarClock, Music2, Bot] as const;

type FeatureCopy = {
  title: string;
  description: string;
};

function PinnedIssueRow({ issue, locale }: { issue: Issue; locale: string }) {
  const { t } = useTranslation();
  const tagName =
    locale === "en" ? (issue.tag.name_en ?? issue.tag.name) :
    locale === "ja" ? (issue.tag.name_ja ?? issue.tag.name) :
    issue.tag.name;
  const { background, border, text } = resolveTagBadgeStyle(issue.tag.color, {
    slug: issue.tag.slug,
    name: issue.tag.name,
  });
  return (
    <Link
      href={`/issues/${issue.id}`}
      className="flex items-start gap-3 p-4 bg-primary/5 hover:bg-primary/10 transition-colors group"
    >
      <div className="mt-0.5 shrink-0">
        <IssueStatusBadge status={issue.status} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="inline-flex items-center rounded-full border text-[10px] px-1.5 py-0.5 leading-none shrink-0 font-semibold"
            style={{ backgroundColor: background, borderColor: border, color: text }}
          >
            {tagName}
          </span>
          <span className="font-medium text-foreground group-hover:text-primary transition-colors leading-snug">
            {issue.title}
          </span>
        </div>
        <p className="text-label text-muted-foreground mt-0.5 flex items-center gap-1 flex-wrap">
          #{issue.id}
          {" · "}
          <span className="inline-flex items-center gap-1">
            {issue.author.is_admin && (
              <ShieldCheck className="h-3.5 w-3.5 text-primary shrink-0" />
            )}
            {t("issues.list.openedBy", { username: issue.author.username })}
          </span>
          {" · "}
          {t("issues.list.created")} {timeAgo(issue.created_at, t)}
          {" · "}
          {t("issues.list.updated")} {timeAgo(issue.last_activity_at, t)}
        </p>
      </div>
      {issue.comment_count > 0 && (
        <div className="shrink-0 flex items-center gap-1 text-label text-muted-foreground">
          <MessageSquare className="h-3.5 w-3.5" />
          {issue.comment_count}
        </div>
      )}
    </Link>
  );
}

export default function HomePage() {
  const { t, i18n } = useTranslation();
  const featureCopies = t("home.features.cards", { returnObjects: true }) as FeatureCopy[];
  const { data: latestAnnouncements } = useAnnouncements({ page: 1, size: 1 });
  const { data: pinnedIssues } = usePinnedIssues(5);
  const latestAnnouncement = latestAnnouncements?.items[0] ?? null;
  const features = featureCopies.map((feature, index) => ({
    ...feature,
    icon: featureIcons[index] ?? Music2,
  }));

  return (
    <>
      <main className="min-h-screen bg-background">
        <Navbar />

        <section className="relative overflow-hidden">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 top-0 h-[32rem]"
            style={{
              background:
                "radial-gradient(circle at top, hsl(var(--primary) / 0.22), hsl(var(--background) / 0) 62%)",
            }}
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute right-0 top-24 h-64 w-64 rounded-full blur-3xl"
            style={{ backgroundColor: "hsl(var(--accent) / 0.15)" }}
          />

          <div className="container relative mx-auto px-4 pb-16 pt-16 md:pb-20 md:pt-20">
            <div className="mx-auto max-w-5xl text-center">
              <div className="flex justify-center">
                <div className="flex items-center gap-3 rounded-full border border-primary/20 bg-background/70 px-4 py-2 text-body font-medium text-primary shadow-sm backdrop-blur">
                  <Music2 className="h-4 w-4" />
                  {t("home.hero.eyebrow")}
                </div>
              </div>

              <div className="mt-8 flex justify-center">
                <Image src="/ojikbms_logo.png" alt="OJIK BMS" width={128} height={128} priority />
              </div>

              <h1 className="mt-8 text-hero font-bold tracking-tight">{t("home.hero.title")}</h1>
              <p className="mx-auto mt-6 max-w-3xl whitespace-pre-line text-xl leading-relaxed text-muted-foreground">
                {t("home.hero.description")}
              </p>

              <div className="mt-10 flex flex-wrap justify-center gap-4">
                <LoginButton />
                <Link href="/download">
                  <Button size="lg" variant="outline" className="gap-2 border-border bg-background/85">
                    <Download className="h-5 w-5" />
                    {t("home.hero.secondaryAction")}
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </section>

        {pinnedIssues && pinnedIssues.length > 0 && (
          <section className="container mx-auto px-4 pb-4 pt-10">
            <div className="rounded-xl border border-border/60 bg-card/60 p-5 shadow-sm backdrop-blur-sm">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/12 text-primary">
                    <Pin className="h-4 w-4 rotate-45" />
                  </div>
                  <h2 className="text-xl font-semibold">{t("issues.discussionIssues")}</h2>
                </div>
                <Link
                  href="/issues"
                  className="group flex items-center gap-1 text-label text-muted-foreground transition-colors hover:text-primary"
                >
                  {t("issues.viewAll")}
                  <span className="transition-transform group-hover:translate-x-0.5">→</span>
                </Link>
              </div>
              <div className="rounded-lg border overflow-hidden">
                <div className="divide-y">
                  {pinnedIssues.map((issue) => (
                    <PinnedIssueRow key={issue.id} issue={issue} locale={i18n.language} />
                  ))}
                </div>
              </div>
            </div>
          </section>
        )}

        {latestAnnouncement && (
          <section className="container mx-auto px-4 pb-4 pt-10">
            <div className="rounded-xl border border-border/60 bg-card/60 p-5 shadow-sm backdrop-blur-sm">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/12 text-primary">
                    <Megaphone className="h-4 w-4" />
                  </div>
                  <h2 className="text-xl font-semibold">{t("announcements.previewTitle")}</h2>
                </div>
                <Link href="/announcements" className="group flex items-center gap-1 text-label text-muted-foreground transition-colors hover:text-primary">
                  {t("announcements.viewAll")}
                  <span className="transition-transform group-hover:translate-x-0.5">→</span>
                </Link>
              </div>
              <AnnouncementCard announcement={latestAnnouncement} preview />
            </div>
          </section>
        )}

        <section className="container mx-auto px-4 py-20">
          <div className="mx-auto max-w-3xl text-center">
            <h2 className="text-3xl font-bold tracking-tight">{t("home.features.title")}</h2>
          </div>

          <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-4">
            {features.map((feature, index) => {
              const Icon = feature.icon;

              return (
                <Card
                  key={feature.title}
                  className="border-border/70 bg-card/85 shadow-sm transition-colors hover:border-primary/40"
                >
                  <CardHeader>
                    <div className="mb-4 flex items-center justify-between">
                      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/12 text-primary">
                        <Icon className="h-6 w-6" />
                      </div>
                      <span className="text-label font-medium text-muted-foreground">
                        {`0${index + 1}`}
                      </span>
                    </div>
                    <CardTitle className="text-lg">{feature.title}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CardDescription className="text-body leading-relaxed text-muted-foreground">
                      {feature.description}
                    </CardDescription>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </section>

        <GuideSection />
      </main>
      <SiteFooter />
    </>
  );
}
