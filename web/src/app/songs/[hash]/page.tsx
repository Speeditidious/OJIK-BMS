"use client";

import { use } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Package, FileCode, Youtube, ExternalLink } from "lucide-react";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FumenTags } from "@/components/fumen/FumenTags";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";
import { formatBpm, formatNotes, formatLength } from "@/lib/bms-format";
import { clearBadge } from "@/components/dashboard/RecentActivity";
import type { DifficultyTable, FumenDetail, UserScore } from "@/types";

interface SongDetailPageProps {
  params: Promise<{ hash: string }>;
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-sm text-muted-foreground w-24 shrink-0">{label}</span>
      <span className="text-sm font-mono">{value}</span>
    </div>
  );
}

export default function SongDetailPage({ params }: SongDetailPageProps) {
  const { hash } = use(params);
  const router = useRouter();
  const { user } = useAuthStore();
  const isLoggedIn = !!user;

  const { data: fumen, isLoading } = useQuery<FumenDetail>({
    queryKey: ["fumen", hash],
    queryFn: () => api.get(`/fumens/${hash}`),
    staleTime: 10 * 60 * 1000,
  });

  const { data: allTables = [] } = useQuery<DifficultyTable[]>({
    queryKey: ["tables"],
    queryFn: () => api.get("/tables/"),
    staleTime: 5 * 60 * 1000,
  });

  const tableSymbolMap = Object.fromEntries(allTables.map((t) => [t.id, t.symbol ?? ""]));

  const { data: scores = [] } = useQuery<UserScore[]>({
    queryKey: ["fumen-scores", hash],
    queryFn: () => api.get(`/scores/me/fumen/${hash}`),
    enabled: isLoggedIn,
    staleTime: 2 * 60 * 1000,
  });

  const effectiveHash = fumen?.sha256 || fumen?.md5 || hash;
  const { total: notesTotal, detail: notesDetail } = formatNotes(
    fumen?.notes_total ?? null,
    fumen?.notes_n ?? null,
    fumen?.notes_ln ?? null,
    fumen?.notes_s ?? null,
    fumen?.notes_ls ?? null,
  );

  // Collect table+level entries
  const tableEntries = fumen?.table_entries ?? [];

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container mx-auto px-4 py-6 max-w-3xl">
        {/* Back button */}
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
              <InfoRow label="Notes" value={notesTotal} />
              {notesDetail && (
                <div className="flex gap-2">
                  <span className="text-sm text-muted-foreground w-24 shrink-0" />
                  <span className="text-xs text-muted-foreground font-mono">{notesDetail}</span>
                </div>
              )}
              <InfoRow label="TOTAL" value={fumen.total !== null ? String(fumen.total) : "-"} />
              <InfoRow label="길이" value={formatLength(fumen.length)} />
            </div>

            {/* Table entries */}
            {tableEntries.length > 0 && (
              <div>
                <h2 className="text-sm font-semibold mb-2 text-muted-foreground uppercase tracking-wide">소속 난이도표</h2>
                <div className="flex flex-wrap gap-2">
                  {tableEntries.map((entry, i) => {
                    const symbol = tableSymbolMap[entry.table_id] ?? "";
                    const levelLabel = `${symbol}${entry.level.replace(symbol, "")}`;
                    return (
                      <Badge key={i} variant="secondary" className="font-mono text-xs">
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
                <h2 className="text-sm font-semibold mb-2 text-muted-foreground uppercase tracking-wide">다운로드</h2>
                <div className="flex gap-3">
                  {fumen.file_url && (
                    <a
                      href={fumen.file_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
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
                      className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
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
                <h2 className="text-sm font-semibold mb-2 text-muted-foreground uppercase tracking-wide">내 태그</h2>
                <FumenTags hash={effectiveHash} />
              </div>
            )}

            {/* Score history */}
            {isLoggedIn && (
              <div>
                <h2 className="text-sm font-semibold mb-2 text-muted-foreground uppercase tracking-wide">내 기록</h2>
                {scores.length === 0 ? (
                  <p className="text-sm text-muted-foreground">기록이 없습니다.</p>
                ) : (
                  <div className="rounded-md border overflow-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-card border-b">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs text-muted-foreground font-medium">클리어</th>
                          <th className="px-3 py-2 text-center text-xs text-muted-foreground font-medium w-16">EX</th>
                          <th className="px-3 py-2 text-center text-xs text-muted-foreground font-medium w-16">Rate</th>
                          <th className="px-3 py-2 text-center text-xs text-muted-foreground font-medium w-12">Rank</th>
                          <th className="px-3 py-2 text-center text-xs text-muted-foreground font-medium w-12">BP</th>
                          <th className="px-3 py-2 text-center text-xs text-muted-foreground font-medium w-10">구동기</th>
                          <th className="px-3 py-2 text-right text-xs text-muted-foreground font-medium">날짜</th>
                        </tr>
                      </thead>
                      <tbody>
                        {scores.map((s) => (
                          <tr key={s.id} className="border-b border-border/30 last:border-0 hover:bg-secondary/30">
                            <td className="px-3 py-2">
                              {clearBadge(s.clear_type, s.client_type)}
                            </td>
                            <td className="px-3 py-2 text-center text-xs font-mono">
                              {s.exscore ?? <span className="text-muted-foreground">--</span>}
                            </td>
                            <td className="px-3 py-2 text-center text-xs font-mono">
                              {s.rate !== null ? `${s.rate.toFixed(1)}%` : <span className="text-muted-foreground">--</span>}
                            </td>
                            <td className="px-3 py-2 text-center text-xs font-mono">
                              {s.rank ?? <span className="text-muted-foreground">--</span>}
                            </td>
                            <td className="px-3 py-2 text-center text-xs font-mono">
                              {s.min_bp ?? <span className="text-muted-foreground">--</span>}
                            </td>
                            <td className="px-3 py-2 text-center">
                              <span className="text-[10px] font-medium border border-border/50 rounded px-1 text-muted-foreground">
                                {s.client_type === "beatoraja" ? "BR" : s.client_type.toUpperCase()}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-right text-xs text-muted-foreground">
                              {s.recorded_at ? new Date(s.recorded_at).toLocaleDateString("ko-KR") : "--"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
