"use client";

import Link from "next/link";
import { useTranslation } from "react-i18next";
import { PublicInfoPageShell } from "@/components/layout/PublicInfoPageShell";

type InfoSection = {
  title: string;
  body: string;
  link?: {
    href: string;
    label: string;
    suffix?: string;
  };
};

export default function SupportPage() {
  const { t } = useTranslation();
  const supportSections = t("support.sections", { returnObjects: true }) as InfoSection[];

  return (
    <PublicInfoPageShell
      title={t("support.title")}
      description={t("support.description")}
    >
      {supportSections.map((section) => (
        <section
          key={section.title}
          className="border-t border-border/70 pt-6 first:border-t-0 first:pt-0"
        >
          <h2 className="text-xl font-semibold tracking-tight">{section.title}</h2>
          <p className="mt-3 text-body leading-relaxed text-muted-foreground">
            {section.body}
            {section.link ? (
              <>
                <Link
                  href={section.link.href}
                  className="font-medium text-foreground underline decoration-border underline-offset-4 transition-colors hover:text-primary hover:decoration-primary"
                >
                  {section.link.label}
                </Link>
                {section.link.suffix}
              </>
            ) : null}
          </p>
        </section>
      ))}
    </PublicInfoPageShell>
  );
}
