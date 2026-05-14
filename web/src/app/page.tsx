"use client";

import Link from "next/link";
import Image from "next/image";
import { Music2, BarChart3, CalendarClock, Bot, Download } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { GuideSection } from "@/components/home/GuideSection";
import { Navbar } from "@/components/layout/navbar";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { LoginButton } from "@/components/home/LoginButton";

const featureIcons = [BarChart3, CalendarClock, Music2, Bot] as const;

type FeatureCopy = {
  title: string;
  description: string;
};

export default function HomePage() {
  const { t } = useTranslation();
  const featureCopies = t("home.features.cards", { returnObjects: true }) as FeatureCopy[];
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
              <p className="mx-auto mt-6 max-w-3xl text-xl leading-relaxed text-muted-foreground">
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
