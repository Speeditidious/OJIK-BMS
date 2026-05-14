"use client";

import Image, { type StaticImageData } from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  Download,
  LayoutDashboard,
  RefreshCw,
  type LucideIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import step1ClientDownloadImage from "../../../public/guide/step1_client_download.png";
import step2ClientSyncImage from "../../../public/guide/step2_client_sync.png";
import step3NavbarDropdownImage from "../../../public/guide/step3_navbar_dropdown.png";

type GuideImage = {
  src: StaticImageData;
  alt: string;
};

type GuideStep = {
  number: string;
  title: string;
  description: string;
  icon: LucideIcon;
  cta?: {
    href: string;
    label: string;
  };
  images: GuideImage[];
};

type GuideStepCopy = {
  title: string;
  description: string;
  ctaLabel?: string;
  imageAlt: string;
};

const guideStepData = [
  {
    number: "01",
    icon: Download,
    cta: {
      href: "/download",
    },
    imageSrc: step1ClientDownloadImage,
  },
  {
    number: "02",
    icon: RefreshCw,
    cta: undefined,
    imageSrc: step2ClientSyncImage,
  },
  {
    number: "03",
    icon: LayoutDashboard,
    cta: undefined,
    imageSrc: step3NavbarDropdownImage,
  },
] as const;

function GuideStepImages({ step }: { step: GuideStep }) {
  if (step.images.length === 1) {
    const image = step.images[0];

    return (
      <div className="relative aspect-[16/10] overflow-hidden rounded-xl border border-border/70 bg-background/80">
        <Image
          src={image.src}
          alt={image.alt}
          fill
          sizes="(min-width: 1024px) 22rem, (min-width: 640px) 60vw, 100vw"
          className="object-cover object-top"
        />
      </div>
    );
  }

  const mainImages = step.images.slice(0, 2);
  const detailImages = step.images.slice(2);

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        {mainImages.map((image) => (
          <div
            key={image.src.src}
            className="relative aspect-[3/5] overflow-hidden rounded-xl border border-border/70 bg-background/80"
          >
            <Image
              src={image.src}
              alt={image.alt}
              fill
              sizes="(min-width: 1024px) 11rem, (min-width: 640px) 30vw, 50vw"
              className="object-cover object-top"
            />
          </div>
        ))}
      </div>
      {detailImages.map((image) => (
        <div
          key={image.src.src}
          className="relative aspect-video overflow-hidden rounded-xl border border-border/70 bg-background/80"
        >
          <Image
            src={image.src}
            alt={image.alt}
            fill
            sizes="(min-width: 1024px) 22rem, (min-width: 640px) 60vw, 100vw"
            className="object-cover object-top"
          />
        </div>
      ))}
    </div>
  );
}

export function GuideSection() {
  const { t } = useTranslation();
  const stepCopies = t("home.guide.steps", { returnObjects: true }) as GuideStepCopy[];
  const guideSteps: GuideStep[] = guideStepData.map((step, index) => {
    const copy = stepCopies[index];

    return {
      number: step.number,
      title: copy.title,
      description: copy.description,
      icon: step.icon,
      cta: step.cta
        ? {
            href: step.cta.href,
            label: copy.ctaLabel ?? "",
          }
        : undefined,
      images: [
        {
          src: step.imageSrc,
          alt: copy.imageAlt,
        },
      ],
    };
  });

  return (
    <section aria-labelledby="guide-title" className="border-t border-border/60 py-20">
      <div className="container mx-auto px-4">
        <div className="mx-auto max-w-3xl text-center">
          <h2 id="guide-title" className="text-3xl font-bold tracking-tight">
            {t("home.guide.title")}
          </h2>
        </div>

        <div className="mt-14 space-y-8">
          {guideSteps.map((step, index) => {
            const Icon = step.icon;
            const isLast = index === guideSteps.length - 1;

            return (
              <article
                key={step.number}
                className="grid gap-5 rounded-[1.75rem] border border-border/70 bg-card/85 p-5 shadow-sm backdrop-blur md:grid-cols-[auto_minmax(0,1fr)] md:gap-8 md:p-6"
              >
                <div className="hidden md:flex md:flex-col md:items-center">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-base font-semibold text-primary-foreground shadow-sm">
                    {step.number}
                  </div>
                  {!isLast ? (
                    <div
                      aria-hidden="true"
                      className="mt-3 w-px flex-1"
                      style={{
                        background:
                          "linear-gradient(180deg, hsl(var(--primary) / 0.6), hsl(var(--border)))",
                      }}
                    />
                  ) : null}
                </div>

                <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(220px,28%)] lg:items-start">
                  <div>
                    <div className="flex items-center gap-3">
                      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/12 text-primary">
                        <Icon className="h-5 w-5" />
                      </div>
                      <div>
                        <div className="text-label font-medium text-primary md:hidden">{step.number}</div>
                        <h3 className="text-xl font-semibold tracking-tight">{step.title}</h3>
                      </div>
                    </div>

                    <p className="mt-4 text-body leading-relaxed text-muted-foreground">
                      {step.description}
                    </p>

                    {step.cta ? (
                      <div className="mt-5">
                        <Button asChild variant="outline" size="lg" className="gap-2">
                          <Link href={step.cta.href}>
                            {step.cta.label}
                            <ArrowRight className="h-4 w-4" />
                          </Link>
                        </Button>
                      </div>
                    ) : null}
                  </div>

                  <GuideStepImages step={step} />
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
