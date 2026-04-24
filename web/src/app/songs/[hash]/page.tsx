"use client";

import { use, useState, useMemo, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Package, FileCode, Youtube, ExternalLink } from "lucide-react";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FumenTags } from "@/components/fumen/FumenTags";
import { api } from "@/lib/api";
import { useUserProfile } from "@/hooks/use-user-profile";
import { useAuthStore } from "@/stores/auth";
import { formatBpm, formatNotes, formatLength } from "@/lib/bms-format";
import { clearText } from "@/components/dashboard/RecentActivity";
import { formatRatePercent } from "@/lib/rate-format";
import { cn } from "@/lib/utils";
import { CLEAR_ROW_CLASS, ARRANGEMENT_KANJI, parseArrangement } from "@/lib/fumen-table-utils";
import type { DifficultyTable, FumenDetail, UserScore } from "@/types";

interface SongDetailPageProps {
  params: Promise<{ hash: string }>;
}

type SortKey = "clear_type" | "exscore" | "rate" | "rank" | "min_bp" | "play_count" | "option" | "client_type" | "recorded_at";
type SortDir = "asc" | "desc";

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-body text-muted-foreground w-24 shrink-0">{label}</span>
      <span className="text-body font-mono">{value}</span>
    </div>
  );
}

function SortIcon({ col, sortKey, sortDir }: { col: SortKey; sortKey: SortKey; sortDir: SortDir }) {
  if (col !== sortKey) return <span className="ml-0.5 text-muted-foreground/35">⇅</span>;
  return <span className="ml-0.5">{sortDir === "asc" ? "↑" : "↓"}</span>;
}

function compareScores(a: UserScore, b: UserScore, key: SortKey, dir: SortDir): number {
  let va: string | number | null = null;
  let vb: string | number | null = null;

  if (key === "clear_type") { va = a.clear_type; vb = b.clear_type; }
  else if (key === "exscore") { va = a.exscore; vb = b.exscore; }
  else if (key === "rate") { va = a.rate; vb = b.rate; }
  else if (key === "rank") { va = a.rank; vb = b.rank; }
  else if (key === "min_bp") { va = a.min_bp; vb = b.min_bp; }
  else if (key === "play_count") { va = a.play_count; vb = b.play_count; }
  else if (key === "option") { va = parseArrangement(a.options, a.client_type) ?? ""; vb = parseArrangement(b.options, b.client_type) ?? ""; }
  else if (key === "client_type") { va = a.client_type; vb = b.client_type; }
  else if (key === "recorded_at") {
    va = a.recorded_at ?? a.synced_at ?? null;
    vb = b.recorded_at ?? b.synced_at ?? null;
  }

  if (va === null && vb === null) return 0;
  if (va === null) return 1;
  if (vb === null) return -1;

  let cmp: number;
  if (typeof va === "string" && typeof vb === "string") {
    cmp = va.localeCompare(vb);
  } else {
    cmp = (va as number) < (vb as number) ? -1 : (va as number) > (vb as number) ? 1 : 0;
  }
  return dir === "asc" ? cmp : -cmp;
}

function ScoreHistorySection({
  title,
  scores,
  isLoading,
  emptyMessage,
  sortKey,
  sortDir,
  onSort,
  thClass,
}: {
  title: string;
  scores: UserScore[];
  isLoading: boolean;
  emptyMessage: string;
  sortKey: SortKey;
  sortDir: SortDir;
  onSort: (key: SortKey) => void;
  thClass: (align?: "left" | "right") => string;
}) {
  return (
    <div>
      <h2 className="text-body font-semibold mb-2 text-muted-foreground uppercase tracking-wide">{title}</h2>
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-10 animate-pulse rounded bg-muted" />
          ))}
        </div>
      ) : scores.length === 0 ? (
        <p className="text-body text-muted-foreground">{emptyMessage}</p>
      ) : (
        <div className="rounded-md border overflow-auto">
          <table className="w-full text-body">
            <thead className="bg-background text-foreground border-b">
              <tr>
                <th className={thClass()} onClick={() => onSort("clear_type")}>
                  클리어<SortIcon col="clear_type" sortKey={sortKey} sortDir={sortDir} />
                </th>
                <th className={thClass()} onClick={() => onSort("min_bp")}>
                  BP<SortIcon col="min_bp" sortKey={sortKey} sortDir={sortDir} />
                </th>
                <th className={thClass()} onClick={() => onSort("rate")}>
                  판정<SortIcon col="rate" sortKey={sortKey} sortDir={sortDir} />
                </th>
                <th className={thClass()} onClick={() => onSort("rank")}>
                  랭크<SortIcon col="rank" sortKey={sortKey} sortDir={sortDir} />
                </th>
                <th className={thClass()} onClick={() => onSort("exscore")}>
                  점수<SortIcon col="exscore" sortKey={sortKey} sortDir={sortDir} />
                </th>
                <th className={thClass()} onClick={() => onSort("play_count")}>
                  플레이 수<SortIcon col="play_count" sortKey={sortKey} sortDir={sortDir} />
                </th>
                <th className={thClass()} onClick={() => onSort("option")}>
                  배치<SortIcon col="option" sortKey={sortKey} sortDir={sortDir} />
                </th>
                <th className={thClass()} onClick={() => onSort("client_type")}>
                  구동기<SortIcon col="client_type" sortKey={sortKey} sortDir={sortDir} />
                </th>
                <th className={thClass()} onClick={() => onSort("recorded_at")}>
                  기록 일시<SortIcon col="recorded_at" sortKey={sortKey} sortDir={sortDir} />
                </th>
              </tr>
            </thead>
            <tbody>
              {scores.map((s) => {
                const arrangementName = parseArrangement(s.options, s.client_type);
                const arrangementKanji = arrangementName ? (ARRANGEMENT_KANJI[arrangementName] ?? arrangementName) : null;
                const rowClass = CLEAR_ROW_CLASS[s.clear_type ?? 0] ?? "";
                const dateStr = s.recorded_at
                  ? new Date(s.recorded_at).toLocaleDateString("ko-KR")
                  : s.is_first_sync
                    ? "--"
                    : s.synced_at
                      ? new Date(s.synced_at).toLocaleDateString("ko-KR")
                      : "--";
                return (
                  <tr key={s.id} className={cn("border-b border-border/30 last:border-0", rowClass || "hover:bg-secondary/50")}>
                    <td className="px-3 py-2">
                      {clearText(s.clear_type, s.client_type)}
                    </td>
                    <td className="px-3 py-2 text-label">
                      {s.min_bp !== null ? s.min_bp : <span className="text-muted-foreground row-muted">--</span>}
                    </td>
                    <td className="px-3 py-2 text-label">
                      {s.rate !== null ? formatRatePercent(s.rate) : <span className="text-muted-foreground row-muted">--</span>}
                    </td>
                    <td className="px-3 py-2 text-label">
                      {s.rank ?? <span className="text-muted-foreground row-muted">--</span>}
                    </td>
                    <td className="px-3 py-2 text-label">
                      {s.exscore !== null ? s.exscore : <span className="text-muted-foreground row-muted">--</span>}
                    </td>
                    <td className="px-3 py-2 text-label">
                      {s.play_count !== null ? s.play_count : <span className="text-muted-foreground row-muted">—</span>}
                    </td>
                    <td className="px-3 py-2 text-label">
                      {arrangementKanji ?? <span className="text-muted-foreground row-muted">—</span>}
                    </td>
                    <td className="px-3 py-2 text-label">
                      <span className="text-label">
                        {s.client_type === "beatoraja" ? "BR" : s.client_type.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-label">
                      {dateStr}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function SongDetailPage({ params }: SongDetailPageProps) {
  const { hash } = use(params);
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuthStore();
  const isLoggedIn = !!user;
  const targetUserId = searchParams.get("user_id");
  const viewingOtherUser = !!targetUserId && targetUserId !== user?.id;

  const [sortKey, setSortKey] = useState<SortKey>("recorded_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const { data: fumen, isLoading } = useQuery<FumenDetail>({
    queryKey: ["fumen", hash],
    queryFn: () => api.get(`/fumens/${hash}`),
    staleTime: 10 * 60 * 1000,
  });

  // Canonical hash: prefer sha256 to ensure LR2+Beatoraja records are both returned by backend
  const effectiveHash = fumen?.sha256 ?? fumen?.md5 ?? hash;

  // Canonical URL redirect: if we entered via md5 but fumen has sha256, replace URL once
  useEffect(() => {
    if (fumen?.sha256 && fumen.sha256 !== hash) {
      const params = searchParams.toString();
      const suffix = params ? `?${params}` : "";
      router.replace(`/songs/${fumen.sha256}${suffix}`);
    }
  }, [fumen?.sha256, hash, router, searchParams]);

  const { data: allTables = [] } = useQuery<DifficultyTable[]>({
    queryKey: ["tables"],
    queryFn: () => api.get("/tables/"),
    staleTime: 5 * 60 * 1000,
  });

  const tableSymbolMap = Object.fromEntries(allTables.map((t) => [t.id, t.symbol ?? ""]));

  const { data: targetProfile } = useUserProfile(targetUserId ?? "");

  const { data: primaryScores = [], isLoading: primaryScoresLoading } = useQuery<UserScore[]>({
    queryKey: ["fumen-scores", effectiveHash, targetUserId ?? user?.id ?? null],
    queryFn: () => {
      const params = new URLSearchParams();
      if (targetUserId) {
        params.set("user_id", targetUserId);
      }
      const suffix = params.size > 0 ? `?${params.toString()}` : "";
      return api.get(`/scores/me/fumen/${effectiveHash}${suffix}`);
    },
    enabled: !!effectiveHash && (!!targetUserId || isLoggedIn),
    staleTime: 2 * 60 * 1000,
  });

  const { data: myScores = [], isLoading: myScoresLoading } = useQuery<UserScore[]>({
    queryKey: ["fumen-scores", effectiveHash, user?.id ?? null, "me"],
    queryFn: () => api.get(`/scores/me/fumen/${effectiveHash}`),
    enabled: isLoggedIn && !!effectiveHash && viewingOtherUser,
    staleTime: 2 * 60 * 1000,
  });

  const sortedPrimaryScores = useMemo(() => {
    return [...primaryScores].sort((a, b) => compareScores(a, b, sortKey, sortDir));
  }, [primaryScores, sortKey, sortDir]);

  const sortedMyScores = useMemo(() => {
    return [...myScores].sort((a, b) => compareScores(a, b, sortKey, sortDir));
  }, [myScores, sortKey, sortDir]);

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "recorded_at" || key === "clear_type" || key === "exscore" ? "desc" : "asc");
    }
  }

  const { total: notesTotal, detail: notesDetail } = formatNotes(
    fumen?.notes_total ?? null,
    fumen?.notes_n ?? null,
    fumen?.notes_ln ?? null,
    fumen?.notes_s ?? null,
    fumen?.notes_ls ?? null,
  );

  const tableEntries = fumen?.table_entries ?? [];

  function thClass(align: "left" | "right" = "left") {
    return `px-3 py-2 text-label cursor-pointer select-none hover:text-primary transition-colors text-${align}`;
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container mx-auto px-4 py-6 max-w-3xl">
        <Button variant="ghost" size="sm" className="-ml-2 mb-4 gap-1.5 text-muted-foreground" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4" />
          뒤로
        </Button>

        {isLoading ? (
          <div className="space-y-4">
            <div className="h-8 w-64 bg-muted rounded animate-pulse" />
            <div className="h-4 w-40 bg-muted rounded animate-pulse" />
          </div>
        ) : !fumen ? (
          <div className="flex items-center justify-center h-64 text-muted-foreground">
            차분을 찾을 수 없습니다.
          </div>
        ) : (
          <div className="space-y-6">
            {/* Title / Artist */}
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-2xl font-bold">{fumen.title || "(제목 없음)"}</h1>
                {fumen.artist && (
                  <p className="text-muted-foreground mt-0.5">{fumen.artist}</p>
                )}
              </div>
              {fumen.youtube_url && (
                <a
                  href={fumen.youtube_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 text-red-400/80 hover:text-red-400 transition-colors"
                  title="YouTube"
                >
                  <Youtube className="h-6 w-6" />
                </a>
              )}
            </div>

            {/* Chart info */}
            <div className="rounded-lg border bg-card p-4 space-y-2">
              <InfoRow label="BPM" value={formatBpm(fumen.bpm_main, fumen.bpm_min, fumen.bpm_max)} />
              <InfoRow label="노트 수" value={notesTotal} />
              {notesDetail && (
                <div className="flex gap-2">
                  <span className="text-body text-muted-foreground w-24 shrink-0" />
                  <span className="text-label text-muted-foreground font-mono">{notesDetail}</span>
                </div>
              )}
              <InfoRow label="TOTAL" value={fumen.total !== null ? String(fumen.total) : "-"} />
              <InfoRow label="곡 길이" value={formatLength(fumen.length)} />
            </div>

            {/* Table entries */}
            {tableEntries.length > 0 && (
              <div>
                <h2 className="text-body font-semibold mb-2 text-muted-foreground uppercase tracking-wide">소속 난이도표</h2>
                <div className="flex flex-wrap gap-2">
                  {tableEntries.map((entry, i) => {
                    const symbol = tableSymbolMap[entry.table_id] ?? "";
                    const levelLabel = `${symbol}${entry.level.replace(symbol, "")}`;
                    return (
                      <Badge key={i} variant="secondary" className="font-mono text-label">
                        {levelLabel}
                      </Badge>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Download links */}
            {(fumen.file_url || fumen.file_url_diff) && (
              <div>
                <h2 className="text-body font-semibold mb-2 text-muted-foreground uppercase tracking-wide">다운로드</h2>
                <div className="flex gap-3">
                  {fumen.file_url && (
                    <a
                      href={fumen.file_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 text-body text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <Package className="h-4 w-4" />
                      동봉
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                  {fumen.file_url_diff && (
                    <a
                      href={fumen.file_url_diff}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 text-body text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <FileCode className="h-4 w-4" />
                      차분
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>
              </div>
            )}

            {/* User tags */}
            {isLoggedIn && (
              <div>
                <h2 className="text-body font-semibold mb-2 text-muted-foreground uppercase tracking-wide">내 태그</h2>
                <FumenTags hash={effectiveHash} />
              </div>
            )}

            {(targetUserId || isLoggedIn) && (
              <div className="space-y-6">
                <ScoreHistorySection
                  title={viewingOtherUser ? `${targetProfile?.username ?? "선택한 유저"}님의 기록` : "내 기록"}
                  scores={sortedPrimaryScores}
                  isLoading={primaryScoresLoading}
                  emptyMessage={viewingOtherUser ? "이 유저의 기록이 없습니다." : "기록이 없습니다."}
                  sortKey={sortKey}
                  sortDir={sortDir}
                  onSort={handleSort}
                  thClass={thClass}
                />
                {viewingOtherUser && isLoggedIn && (
                  <ScoreHistorySection
                    title="내 기록"
                    scores={sortedMyScores}
                    isLoading={myScoresLoading}
                    emptyMessage="내 기록이 없습니다."
                    sortKey={sortKey}
                    sortDir={sortDir}
                    onSort={handleSort}
                    thClass={thClass}
                  />
                )}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
