"use client";

import { cn } from "@/lib/utils";
import type { BracketMeta } from "@/lib/weekly-types";

interface Props {
  brackets: BracketMeta[];
  selected: string;
  onSelect: (bracketKey: string) => void;
}

// ── color utilities ───────────────────────────────────────────────────────────

function relativeLuminance(hex: string): number {
  const n = parseInt(hex.replace("#", ""), 16);
  const [r, g, b] = [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff].map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Lighten a color that would be invisible on a dark (#12151C) background. */
function readableColor(hex: string): string {
  if (relativeLuminance(hex) >= 0.08) return hex;
  const n = parseInt(hex.replace("#", ""), 16);
  const [r, g, b] = [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff].map((c) =>
    Math.min(255, Math.round(c + (255 - c) * 0.55)),
  );
  return "#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("");
}

/** True when the color is light enough that dark text must be used on top of it. */
function needsDarkText(hex: string): boolean {
  const L = relativeLuminance(hex);
  const contrastWhite = 1.05 / (L + 0.05);
  const contrastBlack = (L + 0.05) / 0.05;
  return contrastBlack > contrastWhite;
}

// ── group pill ────────────────────────────────────────────────────────────────

function GroupPill({
  name,
  color,
  active,
  onClick,
}: {
  name: string;
  color: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={
        active
          ? { backgroundColor: color, borderColor: color, boxShadow: `0 0 10px ${color}40` }
          : { backgroundColor: `${color}0d`, borderColor: `${color}40` }
      }
      className={cn(
        "flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm font-semibold transition-all",
        !active && "hover:brightness-110",
      )}
    >
      <span
        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
        style={{ backgroundColor: active ? "rgba(255,255,255,0.7)" : color }}
      />
      <span style={{ color: active ? "#fff" : color }}>{name}</span>
    </button>
  );
}

// ── bracket chip ──────────────────────────────────────────────────────────────

function BracketChip({
  bracket,
  active,
  onClick,
}: {
  bracket: BracketMeta;
  active: boolean;
  onClick: () => void;
}) {
  const { color } = bracket;
  const dark = needsDarkText(color);
  const rangeText = bracket.display_ranges.map((r) => r.text).join(" · ") || "–";

  const rangeColor = active ? (dark ? "rgba(0,0,0,0.75)" : "#fff") : readableColor(color);
  const barColor   = active ? (dark ? "rgba(0,0,0,0.15)" : "rgba(255,255,255,0.25)") : color;

  return (
    <button
      onClick={onClick}
      style={
        active
          ? { backgroundColor: color, borderColor: color, boxShadow: `0 0 10px ${color}40` }
          : { backgroundColor: `${color}0e`, borderColor: `${color}48` }
      }
      className="inline-flex items-stretch rounded-lg border transition-all hover:brightness-110 overflow-hidden"
    >
      <span className="w-1 flex-shrink-0" style={{ backgroundColor: barColor }} />
      <span
        className="px-3 py-2 text-label font-bold tabular-nums whitespace-nowrap flex items-center"
        style={{ color: rangeColor }}
      >
        {rangeText}
      </span>
    </button>
  );
}

// ── main component ────────────────────────────────────────────────────────────

export function WeeklyBracketSelector({ brackets, selected, onSelect }: Props) {
  const uniqueGroups = Array.from(
    new Set(brackets.filter((b) => b.group).map((b) => b.group!)),
  );
  const hasGroups = uniqueGroups.length > 1;

  const activeGroup = hasGroups
    ? (brackets.find((b) => b.key === selected)?.group ?? uniqueGroups[0])
    : null;

  // If selected bracket has no group (null) but groups exist, fall back to the first
  // bracket of the active group so a chip is always visually active.
  const effectiveSelected =
    hasGroups && !brackets.find((b) => b.key === selected)?.group
      ? (brackets.find((b) => b.group === activeGroup)?.key ?? selected)
      : selected;

  const visibleBrackets = hasGroups
    ? brackets.filter((b) => b.group === activeGroup)
    : brackets;

  return (
    <div className="flex flex-col items-center gap-3 w-full">
      {hasGroups && (
        <div className="flex flex-wrap justify-center gap-2">
          {uniqueGroups.map((groupName) => {
            const firstInGroup = brackets.find((b) => b.group === groupName)!;
            return (
              <GroupPill
                key={groupName}
                name={groupName}
                color={firstInGroup.color}
                active={groupName === activeGroup}
                onClick={() => {
                  if (groupName !== activeGroup) onSelect(firstInGroup.key);
                  else if (effectiveSelected !== selected) onSelect(effectiveSelected);
                }}
              />
            );
          })}
        </div>
      )}

      <div className="flex flex-wrap justify-center gap-2">
        {visibleBrackets.map((b) => (
          <BracketChip
            key={b.key}
            bracket={b}
            active={b.key === effectiveSelected}
            onClick={() => onSelect(b.key)}
          />
        ))}
      </div>
    </div>
  );
}
