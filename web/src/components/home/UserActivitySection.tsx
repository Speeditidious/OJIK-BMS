"use client";

import type { ReactNode } from "react";
import { Flame, History, Trophy, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { RecentActivityFeed } from "./RecentActivityFeed";
import { ActivityRankingPanel } from "./ActivityRankingPanel";
import { PopularFumensTable } from "@/components/fumen/PopularFumensTable";

function ActivityPanel({
  icon: Icon,
  title,
  children,
}: {
  icon: LucideIcon;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="flex h-full min-w-0 flex-col">
      <div className="mb-3 flex items-center gap-2">
        <Icon className="h-5 w-5 shrink-0 text-primary" />
        <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
      </div>
      <div className="flex flex-1 flex-col">{children}</div>
    </section>
  );
}

/**
 * Home-page "User Activity" section: recent sync feed, 30-day activity
 * ranking, and the popular-fumens TOP 10 widget, shown side by side as three
 * columns (stacked on narrow viewports).
 *
 * Follows the borderless, center-headed layout of the features/guide sections
 * rather than the bordered card used by the announcements preview.
 *
 * Not wrapped in any conditional by its own logic — this section renders
 * something reasonable even with zero data everywhere, so `page.tsx` can
 * always show it unconditionally.
 *
 * All three panels mount at once, so their APIs are all fetched on load (the
 * previous tabbed version deferred the inactive ones).
 */
export function UserActivitySection() {
  const { t } = useTranslation();

  return (
    <div>
      <div className="mx-auto max-w-3xl text-center">
        <h2 className="text-3xl font-bold tracking-tight">{t("home.activity.title")}</h2>
      </div>

      <div className="mt-12 grid grid-cols-1 gap-8 lg:grid-cols-3">
        <ActivityPanel icon={History} title={t("home.activity.panels.recent")}>
          <RecentActivityFeed />
        </ActivityPanel>

        <ActivityPanel icon={Trophy} title={t("home.activity.panels.ranking")}>
          <ActivityRankingPanel />
        </ActivityPanel>

        <ActivityPanel icon={Flame} title={t("home.activity.panels.popular")}>
          <PopularFumensTable />
        </ActivityPanel>
      </div>
    </div>
  );
}
