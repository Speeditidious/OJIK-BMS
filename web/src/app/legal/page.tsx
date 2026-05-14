"use client";

import { useTranslation } from "react-i18next";
import { PublicInfoPageShell } from "@/components/layout/PublicInfoPageShell";

type InfoSection = {
  title: string;
  body: string;
};

export default function LegalPage() {
  const { t } = useTranslation();
  const legalSections = t("legal.sections", { returnObjects: true }) as InfoSection[];

  return (
    <PublicInfoPageShell
      title={t("legal.title")}
      description={t("legal.description")}
    >
      {legalSections.map((section) => (
        <section
          key={section.title}
          className="border-t border-border/70 pt-6 first:border-t-0 first:pt-0"
        >
          <h2 className="text-xl font-semibold tracking-tight">{section.title}</h2>
          <p className="mt-3 text-body leading-relaxed text-muted-foreground">{section.body}</p>
        </section>
      ))}
    </PublicInfoPageShell>
  );
}
