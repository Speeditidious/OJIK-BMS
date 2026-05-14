"use client";

import { useTranslation } from "react-i18next";
import { PublicInfoPageShell } from "@/components/layout/PublicInfoPageShell";

const keyContributors = [
  { roleKey: "contributors.roles.ratingSystem", name: "모과맛" },
] as const;

const betaTesters = ["모과맛", "서준", "laigus", "Beatnoob", "Kaiden", "Rv", "Artharnal", "민트초코파인트", "scale.out", "칸쥬", "파이알제곱", "모이", "3cchobo", "Siesphere", "RED231", "neonsign", "qodtjr", "Mouse Bul Al", "egosa", "knit700", "bmsnomomdadgame", "dirty_ssamjang", "sadang", "MAID.S", "cr1sp4761", '여긴언더시티팬텀', 'bmslover3shu', 'Hipsta', 'fyjtnbmv', 'nau_0303', 'P02', 'honey2jam', 'relolo', 'arctell', 'paprika_pizza', 'rb_drache', 'farewe11', 'Aesthetica_228', 'lambard', '후아즈', 'kurrsive2000', 'arming_soda', 'buuf5838', 'ggsnipes', 'ys6244', 'sujak663', 'coffeemix', 'hostsamurai_', 'sneoddl1222', 'start_end', 'dibitify_'] as const;

export default function ContributorsPage() {
  const { t } = useTranslation();

  return (
    <PublicInfoPageShell
      title={t("contributors.title")}
      description={t("contributors.description")}
    >
      <section className="border-t border-border/70 pt-6 first:border-t-0 first:pt-0">
        <h2 className="text-xl font-semibold tracking-tight">{t("contributors.developer")}</h2>
        <div className="mt-5 space-y-3">
          <div className="flex items-center gap-2 text-base">
            <span className="text-muted-foreground">-</span>
            <span className="font-semibold">레드볼</span>
            <span className="text-muted-foreground">·</span>
            <span>Discord: RedBall#9777</span>
            <span className="text-muted-foreground">·</span>
            <a
              href="https://github.com/Speeditidious"
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-4 hover:text-foreground transition-colors"
            >
              GitHub: Speeditidious
            </a>
          </div>
        </div>
      </section>

      <section className="border-t border-border/70 pt-6">
        <h2 className="text-xl font-semibold tracking-tight">{t("contributors.keyContributors")}</h2>
        <div className="mt-5 space-y-3">
          {keyContributors.map(({ roleKey, name }) => (
            <div key={name} className="flex items-center gap-2 text-base">
              <span className="text-muted-foreground">-</span>
              <span>{t(roleKey)}:</span>
              <span className="font-semibold">{name}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="border-t border-border/70 pt-6">
        <h2 className="text-xl font-semibold tracking-tight">{t("contributors.betaTesters")}</h2>
        <div className="mt-5 flex flex-wrap gap-2">
          {betaTesters.map((name) => (
            <span
              key={name}
              className="inline-flex items-center rounded-full border border-border bg-card/80 px-4 py-1.5 text-base font-semibold"
            >
              {name}
            </span>
          ))}
        </div>
      </section>
    </PublicInfoPageShell>
  );
}
