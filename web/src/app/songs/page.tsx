"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { Music2, Search } from "lucide-react";

import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent,
  SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { SongListTable } from "@/components/songs/SongListTable";
import { useFumensList } from "@/hooks/use-fumens-list";
import { useAuthStore } from "@/stores/auth";
import { api } from "@/lib/api";
import type { DifficultyTable, FumenSearchField } from "@/types";

const FUMEN_FIELDS = [
  { value: "level",        label: "레벨",          group: "fumen" },
  { value: "title",        label: "제목",          group: "fumen" },
  { value: "artist",       label: "아티스트",       group: "fumen" },
  { value: "clear",        label: "클리어",        group: "score" },
  { value: "bp",           label: "BP",           group: "score" },
  { value: "rate",         label: "판정",          group: "score" },
  { value: "rank",         label: "랭크",          group: "score" },
  { value: "score",        label: "점수",          group: "score" },
  { value: "plays",        label: "플레이",        group: "score" },
  { value: "option",       label: "배치",          group: "score" },
  { value: "env",          label: "구동기",        group: "score" },
  { value: "bpm",          label: "BPM",          group: "fumen" },
  { value: "notes",        label: "노트 수",       group: "fumen" },
  { value: "length",       label: "곡 길이",       group: "fumen" },
] as const;

const ENUM_OPTIONS: Partial<Record<FumenSearchField, readonly string[]>> = {
  clear:  ["MAX", "PERFECT", "FC", "EXHARD", "HARD", "NORMAL", "EASY", "ASSIST", "FAILED", "NO PLAY"],
  rank:   ["AAA", "AA", "A", "B", "C", "D", "E", "F"],
  option: ["正", "鏡", "乱", "R乱", "S乱", "螺", "H乱", "全皿", "EX乱", "EXS乱"],
  env:    ["LR", "BR"],
};

const NUMERIC_PLACEHOLDER: Partial<Record<FumenSearchField, string>> = {
  bpm:    "예: 150 / 120-180 / >=140",
  notes:  "예: 1500 / >=1000",
  length: "예: 2:30 / 1:00-3:00",
  bp:     "예: 0 / <=10",
  rate:   "예: 95.0 / >=90",
  score:  "예: 2000 / >=1800",
  plays:  "예: 10 / >=5",
};

function SongsPageContent() {
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

  const isScoreField = FUMEN_FIELDS.find((f) => f.value === field)?.group === "score";
  const searchDisabled = isScoreField && !isLoggedIn;

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <Navbar />
      <main className="flex-1 min-h-0 container mx-auto px-4 py-6 flex flex-col">
        <div className="mb-3 shrink-0">
          <div className="flex items-center gap-3 mb-1">
            <Music2 className="h-8 w-8 text-primary" />
            <h1 className="text-3xl font-bold">차분 목록</h1>
            {data && (
              <span className="text-body text-muted-foreground">
                총 {data.total.toLocaleString()}건
              </span>
            )}
          </div>
          <p className="text-label text-muted-foreground ml-1">
            현재 서버에 등록되어있는 차분 전체 목록입니다. BPM, 노트 수, 곡 길이와 같은 세부 내용은 그 차분을 소지한 비토라자 유저가 전체 동기화를 했을 때 채워집니다.
          </p>
        </div>

        {/* Search bar */}
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center mb-3 shrink-0">
          <Select value={field} onValueChange={(v) => setField(v as FumenSearchField)}>
            <SelectTrigger className="sm:w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {FUMEN_FIELDS.map((f) =>
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
              <option value="">전체</option>
              {ENUM_OPTIONS[field]!.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          ) : (
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !searchDisabled && commitSearch()}
              placeholder={NUMERIC_PLACEHOLDER[field] ?? "검색어를 입력하세요"}
              className="flex-1"
            />
          )}

          <Button onClick={commitSearch} disabled={searchDisabled}>
            <Search className="h-4 w-4 mr-1" /> 검색
          </Button>
        </div>

        {searchDisabled && (
          <p className="text-label text-destructive mb-2 shrink-0">
            로그인 후 이용할 수 있는 검색 옵션입니다.
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
        <div className="flex items-center justify-center gap-3 mt-3 shrink-0">
          <Button
            variant="outline" size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Prev
          </Button>
          <span className="text-label text-muted-foreground">
            page {page} / {totalPages}
          </span>
          <Button
            variant="outline" size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            Next
          </Button>
        </div>
      </main>
    </div>
  );
}

function SongsPageFallback() {
  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <Navbar />
      <main className="flex-1 min-h-0 container mx-auto px-4 py-6 flex items-center justify-center">
        <div className="text-body text-muted-foreground">불러오는 중...</div>
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
