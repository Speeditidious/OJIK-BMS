"use client";

import { useState } from "react";
import { Activity } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RecentActivityFeed } from "./RecentActivityFeed";
import { ActivityRankingPanel } from "./ActivityRankingPanel";
import { PopularFumensTable } from "@/components/fumen/PopularFumensTable";

type ActivityTab = "recent" | "ranking" | "popular";

const TABS: ActivityTab[] = ["recent", "ranking", "popular"];

/**
 * Home-page "User Activity" section: recent sync feed, 30-day activity
 * ranking, and the popular-fumens TOP 10 widget, behind 3 top-level tabs.
 *
 * Not wrapped in any conditional by its own logic — this section renders
 * something reasonable even with zero data everywhere, so whoever mounts it
 * (a later task, in `page.tsx`) can always show it unconditionally.
 *
 * Only the active tab's content is mounted, so switching tabs defers
 * fetching for the inactive ones instead of firing all 3 APIs up front.
 */
export function UserActivitySection() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<ActivityTab>("recent");

  return (
    <div className="rounded-xl border border-border/60 bg-card/60 p-5 shadow-sm backdrop-blur-sm">
      <div className="mb-4 flex items-center gap-2.5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/12 text-primary">
          <Activity className="h-4 w-4" />
        </div>
        <h2 className="text-xl font-semibold">{t("home.activity.title")}</h2>
      </div>

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as ActivityTab)}>
        <TabsList className="grid w-full grid-cols-3">
          {TABS.map((tab) => (
            <TabsTrigger key={tab} value={tab}>
              {t(`home.activity.tabs.${tab}`)}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <div className="mt-4">
        {activeTab === "recent" && <RecentActivityFeed />}
        {activeTab === "ranking" && <ActivityRankingPanel />}
        {activeTab === "popular" && <PopularFumensTable />}
      </div>
    </div>
  );
}
