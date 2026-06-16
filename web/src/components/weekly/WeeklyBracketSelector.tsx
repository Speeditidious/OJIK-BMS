"use client";

import { Satellite, Sparkle, Star } from "lucide-react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";
import type { BracketMeta } from "@/lib/weekly-types";

const GROUP_ICONS: Record<string, typeof Star> = {
  Starlight: Sparkle,
  Satellite: Satellite,
  Stella: Star,
};

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
function readableOnDark(hex: string): string {
  if (relativeLuminance(hex) >= 0.08) return hex;
  const n = parseInt(hex.replace("#", ""), 16);
  const [r, g, b] = [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff].map((c) =>
    Math.min(255, Math.round(c + (255 - c) * 0.55)),
  );
  return "#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("");
}

/** Darken a color that would be invisible on a light (white) background. */
function readableOnLight(hex: string): string {
  if (relativeLuminance(hex) <= 0.2) return hex;
  const n = parseInt(hex.replace("#", ""), 16);
  const [r, g, b] = [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff].map((c) =>
    Math.max(0, Math.round(c * 0.45)),
  );
  return "#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("");
}

// ── group pill ────────────────────────────────────────────────────────────────

function GroupPill({
  name,
  color,
  endColor,
  active,
  isLightMode,
  onClick,
}: {
  name: string;
  color: string;
  endColor: string;
  active: boolean;
  isLightMode: boolean;
  onClick: () => void;
}) {
  const Icon: typeof Star | undefined = GROUP_ICONS[name];
  const accentColor = isLightMode ? readableOnLight(color) : readableOnDark(color);
  const surfaceColor = isLightMode ? "#ffffff" : "#1E2330";

  const activeStyle: React.CSSProperties = {
    background: `linear-gradient(${surfaceColor}, ${surfaceColor}) padding-box, linear-gradient(90deg, ${color}, ${endColor}) border-box`,
    border: "1.5px solid transparent",
    boxShadow: `0 0 10px ${color}28`,
  };
  const idleStyle: React.CSSProperties = isLightMode
    ? { border: "1.5px solid rgba(0,0,0,.12)" }
    : { border: "1.5px solid rgba(255,255,255,.10)" };

  const textColor = active
    ? isLightMode ? "#1a1d24" : "#e9edf2"
    : accentColor;
  const iconColor = active ? accentColor : `${accentColor}99`;

  return (
    <button
      onClick={onClick}
      style={active ? activeStyle : idleStyle}
      className={cn(
        "flex items-center gap-1.5 px-4 py-2 rounded-lg text-label font-semibold transition-all",
        !active && "hover:brightness-110",
      )}
    >
      {Icon ? (
        <Icon className="w-3.5 h-3.5 flex-shrink-0" style={{ color: iconColor }} />
      ) : (
        <span
          className="w-1.5 h-1.5 rounded-full flex-shrink-0"
          style={{ backgroundColor: iconColor }}
        />
      )}
      <span style={{ color: textColor }}>{name}</span>
    </button>
  );
}

// ── bracket chip ──────────────────────────────────────────────────────────────

function BracketChip({
  bracket,
  active,
  isLightMode,
  onClick,
}: {
  bracket: BracketMeta;
  active: boolean;
  isLightMode: boolean;
  onClick: () => void;
}) {
  const { color } = bracket;
  const accentColor = isLightMode ? readableOnLight(color) : readableOnDark(color);
  const rangeText = bracket.display_ranges.map((r) => r.text).join(" · ") || "–";

  const textColor = active
    ? isLightMode ? "#1a1d24" : "#e9edf2"
    : accentColor;

  return (
    <button
      onClick={onClick}
      style={
        active
          ? {
              backgroundColor: `${color}1e`,
              borderColor: `${color}cc`,
              boxShadow: `0 0 8px ${color}28`,
            }
          : {
              backgroundColor: `${color}0d`,
              borderColor: `${color}40`,
            }
      }
      className="inline-flex items-stretch rounded-lg border transition-all hover:brightness-110 overflow-hidden"
    >
      <span
        className="w-1 flex-shrink-0"
        style={{ backgroundColor: active ? color : `${color}60` }}
      />
      <span
        className="px-3 py-2 text-label font-bold tabular-nums whitespace-nowrap flex items-center"
        style={{ color: textColor }}
      >
        {rangeText}
      </span>
    </button>
  );
}

// ── main component ────────────────────────────────────────────────────────────

export function WeeklyBracketSelector({ brackets, selected, onSelect }: Props) {
  const { resolvedTheme } = useTheme();
  const isLightMode = resolvedTheme !== "dark";

  const uniqueGroups = Array.from(
    new Set(brackets.filter((b) => b.group).map((b) => b.group!)),
  );
  const hasGroups = uniqueGroups.length > 1;

  const activeGroup = hasGroups
    ? (brackets.find((b) => b.key === selected)?.group ?? uniqueGroups[0])
    : null;

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
            const groupBrackets = brackets.filter((b) => b.group === groupName);
            const firstInGroup = groupBrackets[0]!;
            const lastInGroup = groupBrackets[groupBrackets.length - 1]!;
            return (
              <GroupPill
                key={groupName}
                name={groupName}
                color={firstInGroup.color}
                endColor={lastInGroup.color}
                active={groupName === activeGroup}
                isLightMode={isLightMode}
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
            isLightMode={isLightMode}
            onClick={() => onSelect(b.key)}
          />
        ))}
      </div>
    </div>
  );
}
