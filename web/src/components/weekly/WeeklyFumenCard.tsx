"use client";

import { useEffect, useState } from "react";
import { ChevronDown, Star, Check } from "lucide-react";
import { useTranslation } from "react-i18next";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { useWeeklyFumenRecords } from "@/hooks/use-weeklies";
import { useAuthStore } from "@/stores/auth";
import { FumenRowDetail } from "@/components/fumen/FumenRowDetail";
import { AvatarImage } from "@/components/common/AvatarImage";
import { DecoratedUsername } from "@/components/ranking/DecoratedUsername";
import { resolveAvatarUrl } from "@/lib/avatar";
import { formatRatePercent } from "@/lib/rate-format";
import { clearTextColored } from "@/components/dashboard/RecentActivity";
import { parseArrangement, ARRANGEMENT_KANJI, CLEAR_ROW_CLASS } from "@/lib/fumen-table-utils";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { PlayerRecord, WeeklyFumenItem } from "@/lib/weekly-types";

interface Props {
  weeklyId: string;
  item: WeeklyFumenItem;
  myUserId: string | null;
}

function displayLevel(level: string): string {
  return level.replace(/^LEVEL\s+/i, "");
}

const WEEKLY_RECORD_COLGROUP = [
  220,
  96,
  48,
  74,
  60,
  64,
  60,
  68,
  32,
] as const;

function WeeklyRecordColgroup() {
  return (
    <colgroup>
      {WEEKLY_RECORD_COLGROUP.map((width, index) => (
        <col key={index} style={{ width }} />
      ))}
    </colgroup>
  );
}

function WeeklyRecordHeader({
  firstLabel,
  isPinned = false,
}: {
  firstLabel: string;
  isPinned?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <thead>
      <tr>
        <th
          className={cn(
            "px-2 py-1.5 text-xs text-left border-b",
            isPinned
              ? "bg-primary/[0.08] border-primary/20 font-extrabold tracking-widest uppercase text-primary/70"
              : "bg-secondary/30 border-border font-medium text-foreground/60 dark:text-foreground/70",
          )}
        >
          {firstLabel}
        </th>
        {(["clear", "bp", "rate", "rank", "score", "plays", "option"] as const).map((key) => (
          <th
            key={key}
            className={cn(
              "px-2 py-1.5 text-xs font-medium text-foreground/60 dark:text-foreground/70 text-left border-b",
              isPinned ? "bg-primary/[0.08] border-primary/20" : "bg-secondary/30 border-border",
            )}
          >
            {t(`dashboard.scoreUpdates.${key}`)}
          </th>
        ))}
        <th className={cn("w-8 border-b", isPinned ? "bg-primary/[0.08] border-primary/20" : "bg-secondary/30 border-border")} />
      </tr>
    </thead>
  );
}

export function WeeklyFumenCard({ weeklyId, item, myUserId }: Props) {
  const { t } = useTranslation();
  const { user } = useAuthStore();
  const [expanded, setExpanded] = useState(false);
  const [recordsOffset, setRecordsOffset] = useState(0);
  const [pages, setPages] = useState<PlayerRecord[]>([]);
  const [expandedDetailKey, setExpandedDetailKey] = useState<string | null>(null);

  const { data, isLoading } = useWeeklyFumenRecords(weeklyId, item.fumen_id, expanded, recordsOffset, 50);

  useEffect(() => {
    if (!data) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPages((prev) => {
      const seen = new Set(prev.map((r) => r.user_id));
      return [...prev, ...data.records.filter((r) => !seen.has(r.user_id))];
    });
  }, [data]);

  const activeDetailKey = expanded ? expandedDetailKey : null;

  const myRecord = item.my_record;
  const myRecordRow = pages.find((record) => record.user_id === myUserId);
  const pinnedRecord: PlayerRecord | null = myRecord
    ? {
        user_id: myUserId ?? "",
        username: myRecordRow?.username ?? user?.username ?? "",
        avatar_url: myRecordRow?.avatar_url ?? user?.avatar_url ?? null,
        dan_decoration: myRecord.dan_decoration ?? myRecordRow?.dan_decoration ?? null,
        score_id: myRecord.score_id,
        clear_type: myRecord.clear_type,
        exscore: myRecord.exscore,
        rate: myRecord.rate,
        rank: myRecord.rank,
        min_bp: myRecord.min_bp,
        play_count: myRecord.play_count,
        options: myRecord.options,
        client_type: myRecord.client_type,
        improved: myRecord.improved,
        improvement: myRecord.improvement,
      }
    : null;
  const headerRowClass = myRecord ? (CLEAR_ROW_CLASS[myRecord.clear_type ?? 0] ?? "") : "";

  function toggleDetailRow(rowKey: string) {
    setExpandedDetailKey((prev) => (prev === rowKey ? null : rowKey));
  }

  return (
    <TooltipProvider delayDuration={150}>
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        {/* Header row — keeps clear-type background */}
        <div
          className={cn(
            "flex items-center gap-3 px-3 py-3 cursor-pointer select-none transition-colors",
            headerRowClass || "hover:bg-secondary/40",
          )}
          onClick={() => setExpanded((v) => !v)}
        >
          <span className="text-xs font-bold shrink-0 tabular-nums opacity-70">
            {item.table_symbol}{displayLevel(item.level)}
          </span>

          <div className="shrink min-w-0" onClick={(e) => e.stopPropagation()}>
            <Link
              href={item.sha256 ? `/songs/sha256/${item.sha256}` : `/songs/md5/${item.md5}`}
              prefetch={false}
              className="group block"
            >
              <div className="text-sm font-semibold truncate group-hover:underline">
                {item.title ?? "(untitled)"}
              </div>
              <div className="text-xs truncate opacity-50">{item.artist}</div>
            </Link>
          </div>

          <div className="flex-1" />

          {myRecord && (
            <Tooltip>
              <TooltipTrigger asChild>
                {myRecord.improved ? (
                  <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-bold bg-black/15 shrink-0">
                    <Star className="h-3 w-3" />
                    {t("weekly.improved")}
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-semibold bg-black/10 opacity-70 shrink-0">
                    <Check className="h-3 w-3" />
                    {t("weekly.played")}
                  </span>
                )}
              </TooltipTrigger>
              <TooltipContent>
                {myRecord.improved ? t("weekly.improvedTooltip") : t("weekly.playedTooltip")}
              </TooltipContent>
            </Tooltip>
          )}

          <ChevronDown
            className={cn("h-4 w-4 shrink-0 opacity-50 transition-transform duration-200", expanded && "rotate-180")}
          />
        </div>

        {/* Expanded section */}
        {expanded && (
          <div className="border-t border-border">
            {/* MY RECORD pinned card */}
            {pinnedRecord && (
              <div className="mx-2.5 mt-2.5 rounded-md overflow-hidden border border-primary/30 bg-primary/5">
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse" style={{ tableLayout: "fixed", minWidth: 720 }}>
                    <WeeklyRecordColgroup />
                    <WeeklyRecordHeader firstLabel={t("weekly.myRecordSection")} isPinned />
                    <tbody>
                      <RecordRow
                        record={pinnedRecord}
                        isMe
                        isPinned
                        isDetailExpanded={activeDetailKey === `pinned:${pinnedRecord.user_id}`}
                        onToggleDetail={() => toggleDetailRow(`pinned:${pinnedRecord.user_id}`)}
                        fumenId={item.fumen_id}
                      />
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Ranked leaderboard table */}
            <div className="mt-2 overflow-x-auto">
              <table className="w-full border-collapse" style={{ tableLayout: "fixed", minWidth: 720 }}>
                <WeeklyRecordColgroup />
                <WeeklyRecordHeader firstLabel={t("ranking.nickname")} />
                <tbody>
                  {isLoading && pages.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="px-3 py-2 text-xs text-muted-foreground">{t("common.status.loading")}</td>
                    </tr>
                  ) : pages.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="px-3 py-2 text-xs text-muted-foreground">{t("weekly.noRecords")}</td>
                    </tr>
                  ) : (
                    pages.map((record) => (
                      <RecordRow
                        key={record.user_id}
                        record={record}
                        isMe={record.user_id === myUserId}
                        isPinned={false}
                        isDetailExpanded={activeDetailKey === `record:${record.user_id}`}
                        onToggleDetail={() => toggleDetailRow(`record:${record.user_id}`)}
                        fumenId={item.fumen_id}
                      />
                    ))
                  )}
                </tbody>
              </table>

              {data?.next_offset != null && (
                <button
                  onClick={() => setRecordsOffset(data.next_offset ?? 0)}
                  className="w-full px-3 py-2 text-xs hover:bg-secondary/40 transition-colors border-t border-border"
                >
                  {t("weekly.loadMore")}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </TooltipProvider>
  );
}

// ── RecordRow ──────────────────────────────────────────────────────────────

interface RecordRowProps {
  record: PlayerRecord;
  isMe: boolean;
  isPinned: boolean;
  isDetailExpanded: boolean;
  onToggleDetail: () => void;
  fumenId: string;
}

function RecordRow({ record, isMe, isPinned, isDetailExpanded, onToggleDetail, fumenId }: RecordRowProps) {
  const { t } = useTranslation();
  const arrangementName = parseArrangement(record.options ?? null, record.client_type ?? null);
  const arrangementLabel = arrangementName ? (ARRANGEMENT_KANJI[arrangementName] ?? arrangementName) : null;

  const avatarContent = record.avatar_url ? (
    <AvatarImage
      src={resolveAvatarUrl(record.avatar_url)}
      alt={record.username}
      size={28}
      fallbackText={record.username}
      className="rounded-full object-cover block"
    />
  ) : (
    <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center text-[11px] font-bold text-primary shrink-0">
      {record.username ? record.username.charAt(0).toUpperCase() : "?"}
    </div>
  );

  return (
    <>
      <tr
        className={cn(
          "border-b border-border/30 cursor-pointer hover:bg-secondary/30 transition-colors",
          isMe && !isPinned && "bg-primary/5 dark:bg-primary/10",
        )}
        onClick={onToggleDetail}
      >
        {/* User */}
        <td className="px-2 py-2 align-middle">
          <div className="flex items-center gap-2 min-w-0">
            <Link
              href={`/users/${record.user_id}/dashboard`}
              prefetch={false}
              className="inline-flex shrink-0"
              onClick={(e) => e.stopPropagation()}
            >
              {avatarContent}
            </Link>
            <Link
              href={`/users/${record.user_id}/dashboard`}
              prefetch={false}
              className="inline-flex max-w-full min-w-0 cursor-pointer"
              onClick={(e) => e.stopPropagation()}
            >
              <DecoratedUsername
                username={record.username}
                danDecoration={record.dan_decoration}
                className={cn(
                  "text-[15px] leading-none truncate block hover:underline",
                  isPinned ? "font-bold" : "font-semibold",
                )}
              />
            </Link>
          </div>
        </td>

        {/* LAMP — colored text (no row background) */}
        <td className="px-2 py-2 whitespace-nowrap align-middle text-label">
          {record.clear_type != null
            ? clearTextColored(record.clear_type, record.client_type ?? "beatoraja", { exscore: record.exscore, rate: record.rate })
            : <span className="text-label text-muted-foreground/40">—</span>}
        </td>

        {/* BP */}
        <td className="px-2 py-2 text-label tabular-nums align-middle">
          {record.min_bp != null ? record.min_bp : <span className="text-muted-foreground/40">—</span>}
        </td>

        {/* RATE */}
        <td className="px-2 py-2 text-label tabular-nums align-middle">
          {record.rate != null ? formatRatePercent(record.rate) : <span className="text-muted-foreground/40">—</span>}
        </td>

        {/* RANK */}
        <td className="px-2 py-2 text-label tabular-nums align-middle">
          {record.rank ?? <span className="text-muted-foreground/40">—</span>}
        </td>

        {/* SCORE */}
        <td className="px-2 py-2 text-label tabular-nums align-middle">
          {record.exscore ?? <span className="text-muted-foreground/40">—</span>}
        </td>

        {/* PLAYS */}
        <td className="px-2 py-2 text-label tabular-nums align-middle">
          {record.play_count ?? <span className="text-muted-foreground/40">—</span>}
        </td>

        {/* OPTION */}
        <td className="px-2 py-2 text-label align-middle">
          {arrangementLabel ?? <span className="text-muted-foreground/40">—</span>}
        </td>

        {/* Improvement icon (tooltip) */}
        <td className="pr-2 py-2 text-center w-6 align-middle">
          <Tooltip>
            <TooltipTrigger asChild>
              {record.improved ? (
                <span className="inline-flex items-center justify-center w-5 h-5 rounded bg-primary/15 text-primary">
                  <Star className="h-3 w-3" />
                </span>
              ) : (
                <span className="inline-flex items-center justify-center w-5 h-5 rounded bg-secondary/60 opacity-60">
                  <Check className="h-3 w-3" />
                </span>
              )}
            </TooltipTrigger>
            <TooltipContent>
              {record.improved ? t("weekly.improvedTooltip") : t("weekly.playedTooltip")}
            </TooltipContent>
          </Tooltip>
        </td>
      </tr>

      {/* FumenRowDetail sub-row */}
      {isDetailExpanded && (
        <tr>
          <td colSpan={9} className="p-0 border-b border-border/20">
            <div className="border-t border-primary/20 bg-primary/5">
              <FumenRowDetail fumenId={fumenId} scoreId={record.score_id} userId={record.user_id} />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
