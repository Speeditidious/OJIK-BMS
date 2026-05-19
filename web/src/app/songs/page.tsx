"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { Music2, Search } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent,
  SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { SongListTable } from "@/components/songs/SongListTable";
import { Pagination } from "@/components/common/Pagination";
import { useFumensList } from "@/hooks/use-fumens-list";
import { useAuthStore } from "@/stores/auth";
import { api } from "@/lib/api";
import type { DifficultyTable, FumenSearchField } from "@/types";

const FUMEN_FIELD_DEFS = [
  { value: "level",        labelKey: "songs.fields.level",   group: "fumen" },
  { value: "title",        labelKey: "songs.fields.title",   group: "fumen" },
  { value: "artist",       labelKey: "songs.fields.artist",  group: "fumen" },
  { value: "clear",        labelKey: "songs.fields.clear",   group: "score" },
  { value: "bp",           labelKey: "songs.fields.bp",      group: "score" },
  { value: "rate",         labelKey: "songs.fields.rate",    group: "score" },
  { value: "rank",         labelKey: "songs.fields.rank",    group: "score" },
  { value: "score",        labelKey: "songs.fields.score",   group: "score" },
  { value: "plays",        labelKey: "songs.fields.plays",   group: "score" },
  { value: "option",       labelKey: "songs.fields.option",  group: "score" },
  { value: "env",          labelKey: "songs.fields.env",     group: "score" },
  { value: "bpm",          labelKey: "songs.fields.bpm",     group: "fumen" },
  { value: "notes",        labelKey: "songs.fields.notes",   group: "fumen" },
  { value: "length",       labelKey: "songs.fields.length",  group: "fumen" },
] as const;

const ENUM_OPTIONS: Partial<Record<FumenSearchField, readonly string[]>> = {
  clear:  ["MAX", "PERFECT", "FC", "EXHARD", "HARD", "NORMAL", "EASY", "ASSIST", "FAILED", "NO PLAY"],
  rank:   ["AAA", "AA", "A", "B", "C", "D", "E", "F"],
  option: ["正", "鏡", "乱", "R乱", "S乱", "螺", "H乱", "全皿", "EX乱", "EXS乱"],
  env:    ["LR", "BR"],
};

const NUMERIC_PLACEHOLDER: Partial<Record<FumenSearchField, string>> = {
  bpm:    "e.g. 150 / 120-180 / >=140",
  notes:  "e.g. 1500 / >=1000",
  length: "e.g. 2:30 / 1:00-3:00",
  bp:     "e.g. 0 / <=10",
  rate:   "e.g. 95.0 / >=90",
  score:  "e.g. 2000 / >=1800",
  plays:  "e.g. 10 / >=5",
};

function SongsPageContent() {
  const { t } = useTranslation();
  const { user, isInitialized } = useAuthStore();
  const isLoggedIn = isInitialized && !!user;

  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const [field, setField] = useState<FumenSearchField>(
    (sp.get("field") as FumenSearchField) ?? "title"
  );
  const [input, setInput] = useState(sp.get("q") ?? "");
  const [committed, setCommitted] = useState({
    field: (sp.get("field") as FumenSearchField) ?? "title",
    q: sp.get("q") ?? "",
  });
  const [page, setPage] = useState(parseInt(sp.get("page") ?? "1", 10));
  const [sortBy, setSortBy] = useState<string>((sp.get("sort") ?? "title"));
  const [sortDir, setSortDir] = useState<"asc" | "desc">((sp.get("dir") as "asc" | "desc") ?? "asc");

  // URL sync
  useEffect(() => {
    const next = new URLSearchParams();
    next.set("field", committed.field);
    if (committed.q) next.set("q", committed.q);
    if (page !== 1) next.set("page", String(page));
    if (sortBy !== "title") next.set("sort", sortBy);
    if (sortDir !== "asc") next.set("dir", sortDir);
    router.replace(`${pathname}?${next}`, { scroll: false });
  }, [committed, page, sortBy, sortDir, pathname, router]);

  // All tables for symbol map
  const { data: allTables = [] } = useQuery<DifficultyTable[]>({
    queryKey: ["tables"],
    queryFn: () => api.get("/tables/"),
    staleTime: 5 * 60 * 1000,
  });
  const tableSymbolMap = useMemo(
    () => Object.fromEntries(allTables.map((t) => [t.id, t.symbol ?? ""])),
    [allTables]
  );

  const { data, isLoading, isFetching } = useFumensList({
    field: committed.field,
    q: committed.q,
    page,
    sortBy,
    sortDir,
  });

  function commitSearch() {
    setCommitted({ field, q: input });
    setPage(1);
  }

  function handleSort(key: FumenSearchField | "level", dir: "asc" | "desc") {
    setSortBy(key);
    setSortDir(dir);
    setPage(1);
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1;

  const fumenFields = useMemo(
    () => FUMEN_FIELD_DEFS.map((f) => ({ ...f, label: t(f.labelKey) })),
    [t],
  );
  const isScoreField = fumenFields.find((f) => f.value === field)?.group === "score";
  const searchDisabled = isScoreField && !isLoggedIn;

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <Navbar />
      <main className="flex-1 min-h-0 container mx-auto px-4 py-6 flex flex-col">
        <div className="mb-3 shrink-0">
          <div className="flex items-center gap-3 mb-1">
            <Music2 className="h-8 w-8 text-primary" />
            <h1 className="text-3xl font-bold">{t("songs.title")}</h1>
            {data && (
              <span className="text-body text-muted-foreground">
                {t("songs.total", { count: data.total })}
              </span>
            )}
          </div>
          <p className="text-label text-muted-foreground ml-1">
            {t("songs.description")}
          </p>
        </div>

        {/* Search bar */}
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center mb-3 shrink-0">
          <Select value={field} onValueChange={(v) => setField(v as FumenSearchField)}>
            <SelectTrigger className="sm:w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {fumenFields.map((f) =>
                f.group === "score" && !isLoggedIn ? null : (
                  <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>
                )
              )}
            </SelectContent>
          </Select>

          {ENUM_OPTIONS[field] ? (
            <select
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="flex-1 h-10 rounded-md border border-input bg-background px-3 text-body focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">{t("songs.search.all")}</option>
              {ENUM_OPTIONS[field]!.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          ) : (
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !searchDisabled && commitSearch()}
              placeholder={NUMERIC_PLACEHOLDER[field] ?? t("songs.search.placeholder")}
              className="flex-1"
            />
          )}

          <Button onClick={commitSearch} disabled={searchDisabled}>
            <Search className="h-4 w-4 mr-1" /> {t("songs.search.submit")}
          </Button>
        </div>

        {searchDisabled && (
          <p className="text-label text-destructive mb-2 shrink-0">
            {t("songs.search.loginRequired")}
          </p>
        )}

        {/* Table — fills remaining space */}
        <div className="flex-1 min-h-0">
          <SongListTable
            items={data?.items ?? []}
            isLoggedIn={isLoggedIn}
            isLoading={isLoading || isFetching}
            tableSymbolMap={tableSymbolMap}
            sortKey={sortBy}
            sortDir={sortDir}
            onSort={handleSort}
          />
        </div>

        {/* Pagination */}
        <div className="mt-3 shrink-0">
          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            label={t("songs.pagination", { page, totalPages })}
            placeholder={t("pagination.placeholder")}
          />
        </div>
      </main>
    </div>
  );
}

function SongsPageFallback() {
  const { t } = useTranslation();

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <Navbar />
      <main className="flex-1 min-h-0 container mx-auto px-4 py-6 flex items-center justify-center">
        <div className="text-body text-muted-foreground">{t("common.status.loading")}</div>
      </main>
    </div>
  );
}

export default function SongsPage() {
  return (
    <Suspense fallback={<SongsPageFallback />}>
      <SongsPageContent />
    </Suspense>
  );
}
