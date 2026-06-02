"use client";

import { Fragment, use, useState, useMemo, useEffect } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import Link from "next/link";
import { ArrowLeft, Package, FileCode, Youtube, ExternalLink, X } from "lucide-react";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FumenTags } from "@/components/fumen/FumenTags";
import { FumenHistoryRowDetail } from "@/components/fumen/FumenRowDetail";
import { UnavailableValue } from "@/components/common/UnavailableValue";
import { api } from "@/lib/api";
import { songHref, parseSongRouteSegment } from "@/lib/song-href";
import { useUserProfile } from "@/hooks/use-user-profile";
import { useLevelDisplayPrefs } from "@/hooks/use-preferences";
import { useAuthStore } from "@/stores/auth";
import { formatBpm, formatNotes, formatLength } from "@/lib/bms-format";
import { clearText } from "@/components/dashboard/RecentActivity";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { formatRatePercent } from "@/lib/rate-format";
import { formatRelativeDate } from "@/lib/time";
import { displayClearType } from "@/lib/clear-type-display";
import { cn } from "@/lib/utils";
import { CLEAR_ROW_CLASS, ARRANGEMENT_KANJI, parseArrangement } from "@/lib/fumen-table-utils";
import { fumenArtistText, fumenTitleText } from "@/lib/fumen-display";
import { buildFumenExternalLinkGroups, type ExternalHashType, type FumenExternalLink } from "@/lib/fumen-external-links";
import { shouldToggleFumenRow } from "@/lib/fumen-row-toggle-core.mjs";
import type { DifficultyTable, FumenDetail, UserScore } from "@/types";

interface SongDetailPageProps {
  params: Promise<{ fumen_id: string }>;
}

type SortKey = "clear_type" | "exscore" | "rate" | "rank" | "min_bp" | "play_count" | "option" | "recorded_at";
type SortDir = "asc" | "desc";

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-body text-muted-foreground w-24 shrink-0">{label}</span>
      <span className="text-body font-mono">{value}</span>
    </div>
  );
}

function hexContrastColor(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.5 ? "#1a1a2e" : "#ffffff";
}

function ExternalLinksRow({
  label,
  links,
  onMissingHash,
  onOpenLink,
}: {
  label: string;
  links: FumenExternalLink[];
  onMissingHash: (hashType: ExternalHashType) => void;
  onOpenLink: () => void;
}) {
  if (links.length === 0) return null;

  const baseClass = "inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-label transition-all duration-150";
  const plainClass = `${baseClass} border border-border/60 text-muted-foreground hover:text-foreground hover:border-primary/60`;

  function colorStyle(link: FumenExternalLink): React.CSSProperties | undefined {
    if (!link.color) return undefined;
    const textColor = link.textColor ?? hexContrastColor(link.color);
    return { backgroundColor: `${link.color}cc`, color: textColor };
  }

  function handleColorEnter(e: React.MouseEvent<HTMLElement>, link: FumenExternalLink) {
    if (!link.color) return;
    e.currentTarget.style.backgroundColor = link.color;
    e.currentTarget.style.filter = "brightness(1.1)";
  }

  function handleColorLeave(e: React.MouseEvent<HTMLElement>, link: FumenExternalLink) {
    if (!link.color) return;
    e.currentTarget.style.backgroundColor = `${link.color}cc`;
    e.currentTarget.style.filter = "";
  }

  return (
    <div className="flex gap-2 items-center">
      <span className="text-body text-muted-foreground w-24 shrink-0">{label}</span>
      <div className="flex flex-wrap gap-2">
        {links.map((link) => {
          if (link.color) {
            return link.href ? (
              <a
                key={link.name}
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className={`${baseClass} font-medium`}
                style={colorStyle(link)}
                onClick={onOpenLink}
                onMouseEnter={(e) => handleColorEnter(e, link)}
                onMouseLeave={(e) => handleColorLeave(e, link)}
              >
                {link.name}
                <ExternalLink className="h-3 w-3" />
              </a>
            ) : (
              <button
                key={link.name}
                type="button"
                className={`${baseClass} font-medium`}
                style={colorStyle(link)}
                onClick={() => onMissingHash(link.missingHashType!)}
                onMouseEnter={(e) => handleColorEnter(e, link)}
                onMouseLeave={(e) => handleColorLeave(e, link)}
              >
                {link.name}
                <ExternalLink className="h-3 w-3" />
              </button>
            );
          }
          return link.href ? (
            <a
              key={link.name}
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              className={plainClass}
              onClick={onOpenLink}
            >
              {link.name}
              <ExternalLink className="h-3 w-3" />
            </a>
          ) : (
            <button
              key={link.name}
              type="button"
              className={plainClass}
              onClick={() => onMissingHash(link.missingHashType!)}
            >
              {link.name}
              <ExternalLink className="h-3 w-3" />
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SortIcon({ col, sortKey, sortDir }: { col: SortKey; sortKey: SortKey; sortDir: SortDir }) {
  if (col !== sortKey) return <span className="ml-0.5 text-muted-foreground/35">⇅</span>;
  return <span className="ml-0.5">{sortDir === "asc" ? "↑" : "↓"}</span>;
}

function displayScoreRecordedAt(score: UserScore): string | null {
  return score.recorded_at ?? (score.is_first_sync ? null : (score.synced_at ?? null));
}

function sortScoreRecordedAt(score: UserScore): string | null {
  return score.recorded_at ?? score.synced_at ?? null;
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
  else if (key === "recorded_at") {
    va = sortScoreRecordedAt(a);
    vb = sortScoreRecordedAt(b);
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
  const { t } = useTranslation();
  const [expandedScoreIds, setExpandedScoreIds] = useState<Set<string>>(new Set());

  function toggleScore(scoreId: string) {
    setExpandedScoreIds((prev) => {
      const next = new Set(prev);
      if (next.has(scoreId)) next.delete(scoreId); else next.add(scoreId);
      return next;
    });
  }

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
                  {t("common.fields.clear")}<SortIcon col="clear_type" sortKey={sortKey} sortDir={sortDir} />
                </th>
                <th className={thClass()} onClick={() => onSort("min_bp")}>
                  {t("common.fields.bp")}<SortIcon col="min_bp" sortKey={sortKey} sortDir={sortDir} />
                </th>
                <th className={thClass()} onClick={() => onSort("rate")}>
                  {t("common.fields.rate")}<SortIcon col="rate" sortKey={sortKey} sortDir={sortDir} />
                </th>
                <th className={thClass()} onClick={() => onSort("rank")}>
                  {t("common.fields.rank")}<SortIcon col="rank" sortKey={sortKey} sortDir={sortDir} />
                </th>
                <th className={thClass()} onClick={() => onSort("exscore")}>
                  {t("common.fields.score")}<SortIcon col="exscore" sortKey={sortKey} sortDir={sortDir} />
                </th>
                <th className={thClass()} onClick={() => onSort("play_count")}>
                  {t("common.fields.plays")}<SortIcon col="play_count" sortKey={sortKey} sortDir={sortDir} />
                </th>
                <th className={thClass()} onClick={() => onSort("option")}>
                  {t("common.fields.option")}<SortIcon col="option" sortKey={sortKey} sortDir={sortDir} />
                </th>
                <th className={thClass()} onClick={() => onSort("recorded_at")}>
                  {t("common.fields.recordedAt")}<SortIcon col="recorded_at" sortKey={sortKey} sortDir={sortDir} />
                </th>
              </tr>
            </thead>
            <tbody>
              {scores.map((s) => {
                const arrangementName = parseArrangement(s.options, s.client_type);
                const arrangementKanji = arrangementName ? (ARRANGEMENT_KANJI[arrangementName] ?? arrangementName) : null;
                const arrangementReason = s.arrangement?.unavailable_reason ?? null;
                const displayType = displayClearType(s.clear_type, { exscore: s.exscore, rate: s.rate });
                const rowClass = CLEAR_ROW_CLASS[displayType ?? 0] ?? "";
                const effectiveTs = displayScoreRecordedAt(s);
                const sortTs = sortScoreRecordedAt(s);
                const relativeDate = formatRelativeDate(effectiveTs, "--", t);
                const exactDate = effectiveTs ? new Date(effectiveTs).toLocaleDateString("ko-KR") : null;
                const isExpanded = expandedScoreIds.has(s.id);
                return (
                  <Fragment key={s.id}>
                  <tr
                    className={cn("border-b border-border/30 cursor-pointer", rowClass || "hover:bg-secondary/50")}
                    onClick={(event) => {
                      if (!shouldToggleFumenRow(event.target as HTMLElement)) return;
                      toggleScore(s.id);
                    }}
                  >
                    <td className="px-3 py-2">
                      {clearText(s.clear_type, s.client_type, { exscore: s.exscore, rate: s.rate })}
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
                      {arrangementReason
                        ? <UnavailableValue reason={arrangementReason} />
                        : arrangementKanji ?? <span className="text-muted-foreground row-muted">—</span>}
                    </td>
                    <td className="px-3 py-2 text-label">
                      {exactDate ? (
                        <TooltipProvider delayDuration={200}>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="cursor-default">
                                {relativeDate}
                                <span className="ml-0.5 text-accent/70 leading-none">●</span>
                              </span>
                            </TooltipTrigger>
                            <TooltipContent side="top" className="text-label">
                              {exactDate}
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      ) : sortTs ? (
                        <TooltipProvider delayDuration={200}>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="cursor-default text-muted-foreground row-muted">
                                --
                                <span className="ml-0.5 text-accent/70 leading-none">●</span>
                              </span>
                            </TooltipTrigger>
                            <TooltipContent side="top" className="max-w-64 text-label">
                              {t("fumen.detail.firstSyncUnknownDate")}
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      ) : (
                        <span className="text-muted-foreground">--</span>
                      )}
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr key={`${s.id}-detail`}>
                      <td colSpan={8} className="p-0 border-b border-border/20">
                        <div className="border-t border-primary/20 bg-primary/5">
                          <FumenHistoryRowDetail score={s} />
                        </div>
                      </td>
                    </tr>
                  )}
                  </Fragment>
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
  const { t } = useTranslation();
  const { fumen_id: routeFumenIdRaw } = use(params);
  const routeFumenId = parseSongRouteSegment(routeFumenIdRaw);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { user } = useAuthStore();
  const isLoggedIn = !!user;
  const levelDisplayPrefs = useLevelDisplayPrefs();
  const targetUserId = searchParams.get("user_id");
  const viewingOtherUser = !!targetUserId && targetUserId !== user?.id;

  const [sortKey, setSortKey] = useState<SortKey>("recorded_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [missingExternalHash, setMissingExternalHash] = useState<ExternalHashType | null>(null);

  const { data: fumen, isLoading } = useQuery<FumenDetail>({
    queryKey: [
      "fumen",
      routeFumenId,
      user?.id ?? null,
      levelDisplayPrefs.favorite,
      levelDisplayPrefs.server_default,
      levelDisplayPrefs.user_added,
      levelDisplayPrefs.ojik_custom,
      levelDisplayPrefs.favorite_show_non_regular,
      levelDisplayPrefs.server_default_show_non_regular,
      levelDisplayPrefs.user_added_show_non_regular,
      levelDisplayPrefs.ojik_custom_show_non_regular,
    ],
    queryFn: () => api.get(`/fumens/${routeFumenId}`),
    staleTime: 10 * 60 * 1000,
  });

  const effectiveFumenId = fumen?.fumen_id ?? routeFumenId;

  // Canonical URL redirect: resolve to the externally shareable hash URL.
  // If the API cannot resolve a fumen, the original hash URL remains and the page
  // falls through to the normal not-found state.
  useEffect(() => {
    if (!fumen) return;
    const canonical = songHref({
      fumen_id: fumen.fumen_id,
      sha256: fumen.sha256,
      md5: fumen.md5,
    });
    if (canonical !== pathname) {
      const qs = searchParams.toString();
      const suffix = qs ? `?${qs}` : "";
      router.replace(`${canonical}${suffix}`);
    }
  }, [fumen, pathname, router, searchParams]);

  const { data: allTables = [] } = useQuery<DifficultyTable[]>({
    queryKey: ["tables"],
    queryFn: () => api.get("/tables/"),
    staleTime: 5 * 60 * 1000,
  });

  const tableSymbolMap = Object.fromEntries(allTables.map((t) => [t.id, t.symbol ?? ""]));

  const { data: targetProfile } = useUserProfile(targetUserId ?? "");

  const { data: primaryScores = [], isLoading: primaryScoresLoading } = useQuery<UserScore[]>({
    queryKey: ["fumen-scores", effectiveFumenId, targetUserId ?? user?.id ?? null],
    queryFn: () => {
      const params = new URLSearchParams();
      if (targetUserId) {
        params.set("user_id", targetUserId);
      }
      const suffix = params.size > 0 ? `?${params.toString()}` : "";
      return api.get(`/scores/me/fumen/${effectiveFumenId}${suffix}`);
    },
    enabled: !!effectiveFumenId && (!!targetUserId || isLoggedIn),
    staleTime: 2 * 60 * 1000,
  });

  const { data: myScores = [], isLoading: myScoresLoading } = useQuery<UserScore[]>({
    queryKey: ["fumen-scores", effectiveFumenId, user?.id ?? null, "me"],
    queryFn: () => api.get(`/scores/me/fumen/${effectiveFumenId}`),
    enabled: isLoggedIn && !!effectiveFumenId && viewingOtherUser,
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
  const externalLinkGroups = useMemo(
    () => buildFumenExternalLinkGroups({ md5: fumen?.md5, sha256: fumen?.sha256 }),
    [fumen?.md5, fumen?.sha256],
  );

  // Reset the missing-hash banner when the user navigates to a different fumen.
  // React's recommended pattern for "reset state on prop change" — adjust state
  // during render via a previous-value tracker instead of an effect.
  const [prevFumenId, setPrevFumenId] = useState(fumen?.fumen_id);
  if (fumen?.fumen_id !== prevFumenId) {
    setPrevFumenId(fumen?.fumen_id);
    setMissingExternalHash(null);
  }

  function thClass(align: "left" | "right" = "left") {
    return `px-3 py-2 text-label cursor-pointer select-none hover:text-primary transition-colors text-${align}`;
  }

  const displayFumenTitle = fumen ? fumenTitleText(fumen.title, t("fumen.detail.untitled")) : "";
  const displayFumenArtist = fumen ? fumenArtistText(fumen.artist) : "";

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container mx-auto px-4 py-6 max-w-3xl">
        <Button variant="ghost" size="sm" className="-ml-2 mb-4 gap-1.5 text-muted-foreground" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4" />
          {t("fumen.detail.back")}
        </Button>

        {isLoading ? (
          <div className="space-y-4">
            <div className="h-8 w-64 bg-muted rounded animate-pulse" />
            <div className="h-4 w-40 bg-muted rounded animate-pulse" />
          </div>
        ) : !fumen ? (
          <div className="flex items-center justify-center h-64 text-muted-foreground">
            {t("fumen.detail.notFound")}
          </div>
        ) : (
          <div className="space-y-6">
            {/* Title / Artist */}
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-2xl font-bold">{displayFumenTitle}</h1>
                {displayFumenArtist && (
                  <p className="text-muted-foreground mt-0.5">{displayFumenArtist}</p>
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
              <InfoRow label={t("common.fields.notes")} value={notesTotal} />
              {notesDetail && (
                <div className="flex gap-2">
                  <span className="text-body text-muted-foreground w-24 shrink-0" />
                  <span className="text-label text-muted-foreground font-mono">{notesDetail}</span>
                </div>
              )}
              <InfoRow label="TOTAL" value={fumen.total !== null ? String(fumen.total) : "-"} />
              <InfoRow label={t("common.fields.length")} value={formatLength(fumen.length)} />
              {externalLinkGroups.map((group) => (
                <ExternalLinksRow
                  key={group.labelKey}
                  label={t(group.labelKey)}
                  links={group.links}
                  onMissingHash={setMissingExternalHash}
                  onOpenLink={() => setMissingExternalHash(null)}
                />
              ))}
              {missingExternalHash && (
                <div role="alert" className="flex items-start justify-between gap-3 rounded border border-warning/40 bg-warning/10 px-3 py-2 text-label text-warning">
                  <p>{t("fumen.detail.missingExternalHash", { hashType: missingExternalHash })}</p>
                  <button
                    type="button"
                    className="-mr-1 rounded p-0.5 text-warning/80 transition-colors hover:bg-warning/15 hover:text-warning"
                    aria-label={t("common.actions.close")}
                    onClick={() => setMissingExternalHash(null)}
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>

            {/* Table entries */}
            {tableEntries.length > 0 && (
              <div>
                <h2 className="text-body font-semibold mb-2 text-muted-foreground uppercase tracking-wide">{t("fumen.detail.tables")}</h2>
                <div className="flex flex-wrap gap-2">
                  {tableEntries.map((entry, i) => {
                    const symbol = tableSymbolMap[entry.table_id] ?? "";
                    const levelLabel = `${symbol}${entry.level.replace(symbol, "")}`;
                    const tableHref = `/tables?t=${encodeURIComponent(entry.table_id)}&l=${encodeURIComponent(entry.level)}`;
                    return (
                      <Link key={i} href={tableHref}>
                        <Badge variant="secondary" className="text-label cursor-pointer hover:bg-primary/20 transition-colors">
                          {levelLabel}
                        </Badge>
                      </Link>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Download links */}
            {(fumen.file_url || fumen.file_url_diff) && (
              <div>
                <h2 className="text-body font-semibold mb-2 text-muted-foreground uppercase tracking-wide">{t("fumen.detail.download")}</h2>
                <div className="flex gap-3">
                  {fumen.file_url && (
                    <a
                      href={fumen.file_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 text-body text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <Package className="h-4 w-4" />
                      {t("fumen.detail.bundled")}
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
                      {t("fumen.detail.chart")}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>
              </div>
            )}

            {/* User tags */}
            {isLoggedIn && (
              <div>
                <h2 className="text-body font-semibold mb-2 text-muted-foreground uppercase tracking-wide">{t("fumen.detail.myTags")}</h2>
                <FumenTags hash={effectiveFumenId} />
              </div>
            )}

            {(targetUserId || isLoggedIn) && (
              <div className="space-y-6">
                <ScoreHistorySection
                  title={viewingOtherUser ? t("fumen.detail.selectedUserRecords", { username: targetProfile?.username ?? t("common.actions.back") }) : t("fumen.detail.myRecords")}
                  scores={sortedPrimaryScores}
                  isLoading={primaryScoresLoading}
                  emptyMessage={viewingOtherUser ? t("fumen.detail.noSelectedUserRecords") : t("fumen.detail.noMyRecords")}
                  sortKey={sortKey}
                  sortDir={sortDir}
                  onSort={handleSort}
                  thClass={thClass}
                />
                {viewingOtherUser && isLoggedIn && (
                  <ScoreHistorySection
                    title={t("fumen.detail.myRecords")}
                    scores={sortedMyScores}
                    isLoading={myScoresLoading}
                    emptyMessage={t("fumen.detail.noMyRecords")}
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
