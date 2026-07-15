"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { AvatarImage } from "@/components/common/AvatarImage";
import { resolveAvatarUrl } from "@/lib/avatar";
import { BmsforceValue } from "@/components/ranking/BmsforceValue";
import { DecoratedBadge } from "@/components/ranking/DecoratedBadge";
import { DayStatGrid, type DaySummaryData } from "@/components/dashboard/DayStatGrid";
import { DayStatHeaderNote } from "@/components/dashboard/DayStatHeaderNote";
import { useDayNote, type DayNote } from "@/hooks/use-day-notes";
import { UpdateSections } from "@/components/dashboard/UpdateSections";
import { DayStatSheetToolbar } from "@/components/dashboard/DayStatSheetToolbar";
import {
  DayStatSheetPreviewDialog,
  type DayStatSheetExportOptions,
  type DayStatSheetPreviewImage,
} from "@/components/dashboard/DayStatSheetPreviewDialog";
import { TableRatingChangeSection } from "@/components/dashboard/TableRatingChangeSection";
import { useDayStatSheetPrefs, useUpdateDayStatSheetPrefs } from "@/hooks/use-preferences";
import { useMyRank } from "@/hooks/use-rankings";
import { useRatingBreakdown } from "@/hooks/use-analysis";
import { useAuthStore } from "@/stores/auth";
import { captureNodeToPng } from "@/lib/capture-utils";
import { getCaptureErrorMessage } from "@/lib/capture-utils-core.mjs";
import {
  getHeightSplitRanges,
  getSectionSplitGroups,
  shouldShowRatingChangeArea,
} from "@/lib/day-stat-sheet-export-core.mjs";
import type { ScoreUpdatesResponse } from "@/types";
import type { ClientTypeFilter } from "@/hooks/use-analysis";
import type { DanDecoration } from "@/lib/ranking-types";
import { cn } from "@/lib/utils";

interface RankingTableMeta {
  slug: string;
  table_id: string;
  display_name: string;
  display_order: number;
  symbol?: string;
  has_bmsforce: boolean;
}

interface TableHeaderSlotData {
  slug: string;
  bmsforce: number | null;
  danDecoration: DanDecoration | null;
}

interface TableBmsforceChangeData {
  slug: string;
  delta: number | null;
  hasExpChange: boolean;
  hasRatingChange: boolean;
  hasBmsforceChange: boolean;
}

interface DayStatSheetProps {
  userId: string;
  date: string;
  clientType: ClientTypeFilter;
  isOwner: boolean;
  username: string;
  avatarUrl?: string | null;
  rankingTables: RankingTableMeta[];
  daySummary: DaySummaryData | null | undefined;
  scoreUpdatesData: ScoreUpdatesResponse | null | undefined;
}

const DEFAULT_EXPORT_OPTIONS: DayStatSheetExportOptions = {
  mode: "single",
  maxHeight: 1960,
  heightSplitMode: "component",
};

const MAX_HEIGHT_PREVIEW_CACHE_ENTRIES = 5;

function formatSignedShort(v: number): string {
  if (Math.abs(v) < 1e-9) return "-";
  return `${v > 0 ? "+" : ""}${v.toFixed(3)}`;
}

// ── Silent data loader (renders nothing) ──────────────────────────────────────

function TableHeaderDataLoader({
  table,
  userId,
  onData,
}: {
  table: RankingTableMeta;
  userId: string;
  onData: (data: TableHeaderSlotData) => void;
}) {
  const { data } = useMyRank(table.slug, userId);

  useEffect(() => {
    if (data?.status === "ok") {
      onData({
        slug: table.slug,
        bmsforce: data.bms_force > 0 ? data.bms_force : null,
        danDecoration: data.dan_decoration ?? null,
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  return null;
}

function TableBmsforceChangeLoader({
  table,
  userId,
  date,
  onData,
}: {
  table: RankingTableMeta;
  userId: string;
  date: string;
  onData: (data: TableBmsforceChangeData) => void;
}) {
  const { data } = useRatingBreakdown({ tableSlug: table.slug, date, userId });

  useEffect(() => {
    if (data) {
      const total = data.bmsforce_breakdown?.total ?? 0;
      const ratingDelta = data.current.rating - data.previous.rating;
      const expDelta = data.current.exp - data.previous.exp;
      onData({
        slug: table.slug,
        delta: Math.abs(total) > 1e-9 ? total : null,
        hasExpChange: Math.abs(expDelta) > 1e-9,
        hasRatingChange: Math.abs(ratingDelta) > 1e-9,
        hasBmsforceChange: Math.abs(total) > 1e-9,
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  return null;
}

// ── Site branding ─────────────────────────────────────────────────────────────

function SiteHeader() {
  return (
    <div className="flex items-center gap-2">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/ojikbms_logo.png" alt="OJIK BMS" className="h-[26px] w-[26px] rounded-lg" />
      <span className="text-base font-bold tracking-tight">OJIK BMS</span>
    </div>
  );
}

// ── Header card ───────────────────────────────────────────────────────────────

interface BmsforceItem {
  slug: string;
  displayName: string;
  bmsforce: number | null;
  delta: number | null;
}

interface HeaderCardProps {
  userId: string;
  isOwner: boolean;
  showNote: boolean;
  note: DayNote | null | undefined;
  username: string;
  avatarUrl?: string | null;
  date: string;
  danBadges: DanDecoration[];
}

function HeaderCard({ userId, isOwner, showNote, note, username, avatarUrl, date, danBadges }: HeaderCardProps) {
  const { t } = useTranslation();

  return (
    <div className="rounded-2xl border border-border/40 bg-card px-8 py-6 shadow-sm">
      <div className="flex justify-between gap-4 min-w-0">
        {/* Left column: branding + identity, stacked */}
        <div className="flex flex-col gap-5 min-w-0">
          <SiteHeader />

          <div className="flex items-center gap-5 min-w-0">
            <AvatarImage
              src={resolveAvatarUrl(avatarUrl ?? "")}
              alt={username}
              size={96}
              fallbackText={username}
              className="rounded-2xl shrink-0"
            />
            <div className="flex flex-col gap-2 min-w-0 py-2">
              <span className="text-[15px] font-medium text-muted-foreground tabular-nums">
                {date} · {t("dashboard.daySheet.reportTitle")}
                <span data-day-sheet-page-indicator className="hidden" />
              </span>

              <div className="flex items-center gap-4 flex-wrap">
                <span className="text-[38px] font-extrabold tracking-[-0.02em] text-foreground leading-none">
                  {username}
                </span>

                {danBadges.length > 0 && (
                  <>
                    <div className="w-px self-stretch bg-border/60 shrink-0" />
                    <div className="flex flex-col gap-1">
                      <span className="text-[13px] font-semibold text-muted-foreground uppercase tracking-widest">
                        {t("dashboard.daySheet.danLabel")}
                      </span>
                      <div className="flex items-center gap-4 flex-wrap">
                        {danBadges.map((badge) => (
                          <DecoratedBadge
                            key={badge.display_text}
                            text={badge.display_text}
                            decoration={badge}
                            className="text-[23px] font-extrabold leading-none"
                          />
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Right column: memo region spanning the full card height */}
        {showNote && (
          <div className="flex-1 self-stretch min-w-0 flex items-center justify-center">
            <DayStatHeaderNote userId={userId} date={date} isOwner={isOwner} note={note} />
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function DayStatSheet({
  userId,
  date,
  clientType: _clientType,
  isOwner,
  username,
  avatarUrl,
  rankingTables,
  daySummary,
  scoreUpdatesData,
}: DayStatSheetProps) {
  const { t } = useTranslation();
  const { data: dayNote } = useDayNote(userId, date);
  const exportRef = useRef<HTMLDivElement>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [previewImages, setPreviewImages] = useState<DayStatSheetPreviewImage[]>([]);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [previewRequestId, setPreviewRequestId] = useState(0);
  const [exportOptions, setExportOptions] = useState<DayStatSheetExportOptions>(DEFAULT_EXPORT_OPTIONS);
  const previewCacheRef = useRef<Map<string, DayStatSheetPreviewImage[]>>(new Map());
  const previewPendingRef = useRef<Map<string, Promise<DayStatSheetPreviewImage[]>>>(new Map());
  const heightPreviewCacheKeysRef = useRef<string[]>([]);

  // ── Lifted state (was inside HeaderCard) ──────────────────────────────────
  const [tableDataMap, setTableDataMap] = useState<Record<string, TableHeaderSlotData>>({});
  const [bmsforceChangeMap, setBmsforceChangeMap] = useState<Record<string, TableBmsforceChangeData>>({});

  const handleData = useCallback((data: TableHeaderSlotData) => {
    setTableDataMap((prev) => ({ ...prev, [data.slug]: data }));
  }, []);

  const handleChangeData = useCallback((data: TableBmsforceChangeData) => {
    setBmsforceChangeMap((prev) => ({ ...prev, [data.slug]: data }));
  }, []);

  const prefs = useDayStatSheetPrefs();
  const { mutate: updatePrefsRaw } = useUpdateDayStatSheetPrefs();
  // Always send the full merged prefs so the server's shallow merge
  // doesn't overwrite unrelated day_sheet_prefs fields.
  const updatePrefs = useCallback(
    (partial: Partial<typeof prefs>) => updatePrefsRaw({ ...prefs, ...partial }),
    [prefs, updatePrefsRaw],
  );
  const { user, isInitialized } = useAuthStore();
  const canPersist = isInitialized && !!user;

  // ── Table selection + ordering ─────────────────────────────────────────────
  // When day_sheet_tables is non-null, its array order defines display order.
  // When null, auto-detect from tables with has_bmsforce, sorted by display_order.
  const selectedTables = useMemo(() => {
    const slugs = prefs.day_sheet_tables;
    if (slugs === null) {
      return rankingTables
        .filter((t) => t.has_bmsforce)
        .sort((a, b) => a.display_order - b.display_order);
    }
    return slugs
      .map((slug) => rankingTables.find((t) => t.slug === slug))
      .filter((t): t is RankingTableMeta => t != null);
  }, [prefs.day_sheet_tables, rankingTables]);

  // ── Dan badges with optional user-defined ordering ─────────────────────────
  const danBadges = useMemo(() => {
    const seen = new Set<string>();
    const autoOrder: DanDecoration[] = [];
    for (const table of selectedTables) {
      const d = tableDataMap[table.slug]?.danDecoration;
      if (d && !seen.has(d.display_text)) {
        seen.add(d.display_text);
        autoOrder.push(d);
      }
    }

    if (!prefs.day_sheet_dan_order) return autoOrder;

    const ordered = prefs.day_sheet_dan_order
      .map((text) => autoOrder.find((d) => d.display_text === text))
      .filter((d): d is DanDecoration => d != null);
    const rest = autoOrder.filter((d) => !prefs.day_sheet_dan_order!.includes(d.display_text));
    return [...ordered, ...rest];
  }, [selectedTables, tableDataMap, prefs.day_sheet_dan_order]);

  // ── BMSFORCE items ─────────────────────────────────────────────────────────
  const bmsforceItems = useMemo(
    () =>
      selectedTables.map((t) => ({
        slug: t.slug,
        displayName: t.display_name,
        bmsforce: tableDataMap[t.slug]?.bmsforce ?? null,
        delta: bmsforceChangeMap[t.slug]?.delta ?? null,
      })),
    [selectedTables, tableDataMap, bmsforceChangeMap],
  );

  const showRatingChangeArea = useMemo(
    () =>
      shouldShowRatingChangeArea({
        selectedTableSlugs: selectedTables.map((table) => table.slug),
        tableChangesBySlug: bmsforceChangeMap,
        mode: prefs.day_sheet_rating_display_mode,
      }),
    [selectedTables, bmsforceChangeMap, prefs.day_sheet_rating_display_mode],
  );

  // display_texts of dan badges available for ordering in toolbar
  const availableDans = useMemo(() => danBadges.map((d) => d.display_text), [danBadges]);

  const filename = `ojikbms_${date}_${username}.png`;

  function handlePreview() {
    if (!exportRef.current) return;
    setIsSaving(true);
    setSaveError(null);
    setPreviewImages([]);
    setIsPreviewOpen(true);
    setPreviewRequestId((id) => id + 1);
  }

  const handlePreviewClose = useCallback(() => {
    setIsPreviewOpen(false);
    setIsSaving(false);
    setPreviewImages([]);
    previewCacheRef.current.clear();
    previewPendingRef.current.clear();
    heightPreviewCacheKeysRef.current = [];
  }, []);

  useEffect(() => {
    if (!isPreviewOpen || !exportRef.current) return;

    let cancelled = false;
    const source = exportRef.current;
    const cacheKey = makePreviewCacheKey(exportOptions);
    const cached = previewCacheRef.current.get(cacheKey);
    if (cached) {
      setIsSaving(false);
      setSaveError(null);
      setPreviewImages(cached);
      if (exportOptions.mode === "height") {
        touchHeightPreviewCacheKey(heightPreviewCacheKeysRef.current, cacheKey);
      }
      return;
    }

    async function generatePreviewImages() {
      setIsSaving(true);
      setSaveError(null);
      setPreviewImages([]);

      try {
        let pending = previewPendingRef.current.get(cacheKey);
        if (!pending) {
          pending = waitForPaint().then(() => captureSheetImages(source, exportOptions, filename, t));
          previewPendingRef.current.set(cacheKey, pending);
        }
        const images = await pending;
        previewPendingRef.current.delete(cacheKey);
        cachePreviewImages(previewCacheRef.current, heightPreviewCacheKeysRef.current, cacheKey, exportOptions.mode, images);
        if (!cancelled) setPreviewImages(images);
      } catch (err) {
        previewPendingRef.current.delete(cacheKey);
        if (cancelled) return;
        const msg = getCaptureErrorMessage(err);
        console.error("capture day stat sheet failed", err);
        setSaveError(`${t("dashboard.scoreUpdates.imageSaveFailed")}: ${msg}`);
      } finally {
        if (!cancelled) setIsSaving(false);
      }
    }

    void generatePreviewImages();

    return () => {
      cancelled = true;
    };
  }, [exportOptions, filename, isPreviewOpen, previewRequestId, t]);

  return (
    <div className="space-y-4">
      {/* Silent data loaders — render nothing, just fire callbacks */}
      {selectedTables.map((t) => (
        <TableHeaderDataLoader key={t.slug} table={t} userId={userId} onData={handleData} />
      ))}
      {selectedTables.map((t) => (
        <TableBmsforceChangeLoader
          key={`change-${t.slug}`}
          table={t}
          userId={userId}
          date={date}
          onData={handleChangeData}
        />
      ))}

      {/* Toolbar — outside export canvas */}
      <DayStatSheetToolbar
        allTables={rankingTables}
        prefs={prefs}
        onPrefsChange={updatePrefs}
        onSave={handlePreview}
        isSaving={isSaving}
        saveError={saveError}
        availableDans={availableDans}
      />

      {/* Export canvas */}
      <div
        ref={exportRef}
        className={cn("space-y-4 rounded-xl border border-border/50 bg-background p-4")}
      >
        {selectedTables.length > 0 ? (
          <div data-day-sheet-section="profile" data-day-sheet-split-block>
            <HeaderCard
              userId={userId}
              isOwner={isOwner}
              showNote={prefs.day_sheet_show_note}
              note={dayNote}
              username={username}
              avatarUrl={avatarUrl}
              date={date}
              danBadges={danBadges}
            />
          </div>
        ) : (
          <div
            data-day-sheet-section="profile"
            data-day-sheet-split-block
            className="rounded-2xl border border-border/40 bg-card px-8 py-5 shadow-sm"
          >
            <div className="flex justify-between gap-3 min-w-0">
              {/* Left column: branding + identity, stacked */}
              <div className="flex flex-col gap-4 min-w-0">
                <SiteHeader />
                <div className="flex items-center gap-3 min-w-0">
                  <AvatarImage
                    src={resolveAvatarUrl(avatarUrl ?? "")}
                    alt={username}
                    size={44}
                    fallbackText={username}
                    className="rounded-xl shrink-0"
                  />
                  <div className="flex flex-col gap-0.5">
                    <span className="text-xl font-bold text-foreground">{username}</span>
                    <span className="text-sm text-muted-foreground tabular-nums">
                      {date} · {t("dashboard.daySheet.reportTitle")}
                      <span data-day-sheet-page-indicator className="hidden" />
                    </span>
                  </div>
                </div>
              </div>
              {prefs.day_sheet_show_note && (
                <div className="flex-1 self-stretch min-w-0 flex items-center justify-center">
                  <DayStatHeaderNote userId={userId} date={date} isOwner={isOwner} note={dayNote} />
                </div>
              )}
            </div>
          </div>
        )}

        {daySummary && (
          <div data-day-sheet-section="summary" data-day-sheet-split-block>
            <DayStatGrid daySummary={daySummary} />
          </div>
        )}

        {prefs.day_sheet_show_rating_section && showRatingChangeArea && (
          <div data-day-sheet-section="rating" className="space-y-6">
            {/* Section header */}
            <div data-day-sheet-split-block data-day-sheet-keep-with-next className="mt-4 flex items-center gap-3">
              <div className="flex-1 border-t border-border/50" />
              <h2 className="shrink-0 text-2xl font-extrabold tracking-tight text-foreground">
                {t("dashboard.daySheet.ratingChanges")}
              </h2>
              <div className="flex-1 border-t border-border/50" />
            </div>

            {/* BMSFORCE grid — moved from HeaderCard */}
            {bmsforceItems.some((item) => item.bmsforce != null) && (
              <div data-day-sheet-split-block className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
                {bmsforceItems.map((item) => (
                  <div
                    key={item.slug}
                    className="flex flex-col gap-0.5 rounded-xl border border-border/50 bg-secondary/30 px-4 py-3"
                  >
                    <span className="text-[12px] font-semibold text-muted-foreground uppercase tracking-wide truncate">
                      {item.displayName}
                    </span>
                    <BmsforceValue
                      value={item.bmsforce}
                      className="text-[26px] font-extrabold tabular-nums leading-none"
                    />
                    <span
                      className="text-[13px] font-bold tabular-nums leading-none"
                      style={{
                        color: item.delta != null && item.delta > 0
                          ? "hsl(var(--accent))"
                          : "hsl(var(--muted-foreground))",
                      }}
                    >
                      {item.delta != null ? formatSignedShort(item.delta) : "-"}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Per-table rating sections */}
            {selectedTables.map((table) => (
              <TableRatingChangeSection
                key={table.slug}
                tableSlug={table.slug}
                tableDisplayName={table.display_name}
                date={date}
                userId={userId}
                showExpInfo={prefs.day_sheet_show_exp_info}
                showRatingInfo={prefs.day_sheet_show_rating_info}
                ratingOrder={prefs.day_sheet_rating_order}
                displayMode={prefs.day_sheet_rating_display_mode}
                isOwner={isOwner}
              />
            ))}
          </div>
        )}

        {prefs.day_sheet_show_record_section && scoreUpdatesData && (
          <div data-day-sheet-section="record" className="space-y-4">
            <div data-day-sheet-split-block data-day-sheet-keep-with-next className="mt-4 flex items-center gap-3">
              <div className="flex-1 border-t border-border/50" />
              <h2 className="shrink-0 text-2xl font-extrabold tracking-tight text-foreground">
                {t("dashboard.daySheet.recordOptions")}
              </h2>
              <div className="flex-1 border-t border-border/50" />
            </div>
            <UpdateSections
              data={scoreUpdatesData}
              userId={userId}
              asOf={date}
              prefs={prefs}
              onPrefsChange={canPersist ? updatePrefs : undefined}
              variant="sheet"
            />
          </div>
        )}
      </div>

      <DayStatSheetPreviewDialog
        open={isPreviewOpen}
        images={previewImages}
        isGenerating={isSaving}
        options={exportOptions}
        onOptionsChange={setExportOptions}
        onClose={handlePreviewClose}
      />
    </div>
  );
}

function makePreviewCacheKey(options: DayStatSheetExportOptions): string {
  if (options.mode !== "height") return options.mode;
  return `${options.mode}:${options.maxHeight}:${options.heightSplitMode}`;
}

function touchHeightPreviewCacheKey(keys: string[], key: string) {
  const existingIndex = keys.indexOf(key);
  if (existingIndex !== -1) keys.splice(existingIndex, 1);
  keys.push(key);
}

function cachePreviewImages(
  cache: Map<string, DayStatSheetPreviewImage[]>,
  heightKeys: string[],
  key: string,
  mode: DayStatSheetExportOptions["mode"],
  images: DayStatSheetPreviewImage[],
) {
  cache.set(key, images);
  if (mode !== "height") return;

  touchHeightPreviewCacheKey(heightKeys, key);
  while (heightKeys.length > MAX_HEIGHT_PREVIEW_CACHE_ENTRIES) {
    const oldest = heightKeys.shift();
    if (oldest) cache.delete(oldest);
  }
}

function waitForPaint(): Promise<void> {
  return new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  });
}

async function captureSheetImages(
  source: HTMLElement,
  options: DayStatSheetExportOptions,
  filename: string,
  t: (key: string, options?: Record<string, unknown>) => string,
): Promise<DayStatSheetPreviewImage[]> {
  if (options.mode === "single") {
    const { dataUrl } = await captureNodeToPng(source);
    return [{ dataUrl, filename, label: t("dashboard.daySheet.exportSingle") }];
  }

  if (options.mode === "sections") {
    return captureSectionImages(source, filename, t);
  }

  return captureHeightImages(source, options, filename, t);
}

async function captureSectionImages(
  source: HTMLElement,
  filename: string,
  t: (key: string, options?: Record<string, unknown>) => string,
): Promise<DayStatSheetPreviewImage[]> {
  const sectionIds = Array.from(source.querySelectorAll<HTMLElement>("[data-day-sheet-section]"))
    .map((section) => section.dataset.daySheetSection)
    .filter((id): id is string => id != null);
  const groups = getSectionSplitGroups([...new Set(sectionIds)]);

  if (groups.length === 1) {
    const { dataUrl } = await captureNodeToPng(source);
    return [{ dataUrl, filename, label: t("dashboard.daySheet.exportSingle") }];
  }

  const images: DayStatSheetPreviewImage[] = [];
  for (const [index, group] of groups.entries()) {
    const clone = source.cloneNode(true) as HTMLElement;
    const allowed = new Set(group);
    clone.querySelectorAll<HTMLElement>("[data-day-sheet-section]").forEach((section) => {
      const sectionId = section.dataset.daySheetSection;
      if (!sectionId || !allowed.has(sectionId)) section.remove();
    });
    setCapturePageIndicator(clone, index + 1, groups.length);
    const dataUrl = await captureDetachedElement(source, clone);
    images.push({
      dataUrl,
      filename: withFileSuffix(filename, index + 1),
      label: t("dashboard.daySheet.exportPageLabel", { page: index + 1 }),
    });
  }
  return images;
}

async function captureHeightImages(
  source: HTMLElement,
  options: DayStatSheetExportOptions,
  filename: string,
  t: (key: string, options?: Record<string, unknown>) => string,
): Promise<DayStatSheetPreviewImage[]> {
  const parentRect = source.getBoundingClientRect();
  const splitBlockElements = source.querySelectorAll<HTMLElement>("[data-day-sheet-split-block]");
  const measuredElements = splitBlockElements.length > 0
    ? Array.from(splitBlockElements)
    : Array.from(source.children).filter((child): child is HTMLElement => child instanceof HTMLElement);
  const blocks = measuredElements
    .map((child) => {
      const rect = child.getBoundingClientRect();
      return {
        id: child.dataset.daySheetSection ?? "",
        top: rect.top - parentRect.top,
        bottom: rect.bottom - parentRect.top,
        keepWithNext: child.hasAttribute("data-day-sheet-keep-with-next"),
      };
    });
  const ranges = getHeightSplitRanges(blocks, {
    maxHeight: options.maxHeight,
    preserveBlocks: options.heightSplitMode === "component",
  });

  if (ranges.length <= 1) {
    const { dataUrl } = await captureNodeToPng(source);
    return [{ dataUrl, filename, label: t("dashboard.daySheet.exportSingle") }];
  }

  const images: DayStatSheetPreviewImage[] = [];
  for (const [index, range] of ranges.entries()) {
    const clone = source.cloneNode(true) as HTMLElement;
    const slice = document.createElement("div");
    slice.style.width = `${source.offsetWidth}px`;
    slice.style.display = "block";
    slice.style.height = `${range.bottom - range.top}px`;
    slice.style.overflow = "hidden";
    slice.style.background = getComputedStyle(source).backgroundColor;
    clone.style.transform = `translateY(-${range.top}px)`;
    clone.style.width = `${source.offsetWidth}px`;
    setCapturePageIndicator(clone, index + 1, ranges.length);
    slice.appendChild(clone);
    const dataUrl = await captureDetachedElement(source, slice);
    images.push({
      dataUrl,
      filename: withFileSuffix(filename, index + 1),
      label: t("dashboard.daySheet.exportPageLabel", { page: index + 1 }),
    });
  }
  return images;
}

function setCapturePageIndicator(element: HTMLElement, page: number, pageCount: number) {
  if (pageCount <= 1) return;
  element.querySelectorAll<HTMLElement>("[data-day-sheet-page-indicator]").forEach((indicator) => {
    indicator.textContent = ` ${page}/${pageCount}`;
    indicator.classList.remove("hidden");
  });
}

async function captureDetachedElement(source: HTMLElement, element: HTMLElement): Promise<string> {
  const host = document.createElement("div");
  host.style.position = "fixed";
  host.style.left = "-10000px";
  host.style.top = "0";
  host.style.width = `${source.offsetWidth}px`;
  host.style.pointerEvents = "none";
  host.style.zIndex = "-1";
  element.style.width = `${source.offsetWidth}px`;
  host.appendChild(element);
  document.body.appendChild(host);

  try {
    await waitForPaint();
    const { dataUrl } = await captureNodeToPng(element);
    return dataUrl;
  } finally {
    host.remove();
  }
}

function withFileSuffix(filename: string, index: number): string {
  const dotIndex = filename.lastIndexOf(".");
  if (dotIndex === -1) return `${filename}_${index}`;
  return `${filename.slice(0, dotIndex)}_${index}${filename.slice(dotIndex)}`;
}
