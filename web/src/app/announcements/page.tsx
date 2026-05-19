"use client";

import { Suspense, useState } from "react";
import { Megaphone } from "lucide-react";
import { useTranslation } from "react-i18next";
import { AnnouncementCard } from "@/components/announcements/AnnouncementCard";
import { Pagination } from "@/components/common/Pagination";
import { Navbar } from "@/components/layout/navbar";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAnnouncements, useAnnouncementTags } from "@/hooks/use-announcements";

function AnnouncementsContent() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const [page, setPage] = useState(1);
  const [tag, setTag] = useState("all");
  const { data } = useAnnouncements({ page, size: 10, tag: tag === "all" ? undefined : tag });
  const { data: tags = [] } = useAnnouncementTags();

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container mx-auto px-4 py-8">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <Megaphone className="h-7 w-7 text-primary" />
              <h1 className="text-3xl font-bold">{t("announcements.title")}</h1>
            </div>
            <p className="mt-2 text-body text-muted-foreground">{t("announcements.description")}</p>
          </div>
          <Select
            value={tag}
            onValueChange={(value) => {
              setTag(value);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-full sm:w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("announcements.allTags")}</SelectItem>
              {tags.map((item) => {
                const tagName = lang.startsWith("en")
                  ? (item.name_en ?? item.name)
                  : lang.startsWith("ja")
                    ? (item.name_ja ?? item.name)
                    : item.name;
                return (
                  <SelectItem key={item.id} value={item.id}>
                    {tagName}
                  </SelectItem>
                );
              })}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-4">
          {data?.items.map((announcement) => (
            <AnnouncementCard key={announcement.id} announcement={announcement} />
          ))}
          {data && data.items.length === 0 && (
            <p className="rounded-lg border py-12 text-center text-body text-muted-foreground">
              {t("announcements.empty")}
            </p>
          )}
        </div>

        {data && data.pages > 1 && (
          <div className="mt-6">
            <Pagination
              page={page}
              totalPages={data.pages}
              onPageChange={setPage}
              label={t("pagination.label", { page, totalPages: data.pages })}
              placeholder={t("pagination.placeholder")}
            />
          </div>
        )}
      </main>
    </div>
  );
}

export default function AnnouncementsPage() {
  return (
    <Suspense>
      <AnnouncementsContent />
    </Suspense>
  );
}
