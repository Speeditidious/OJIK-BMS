"use client";

import { cn } from "@/lib/utils";
import type { DanDecoration } from "@/lib/ranking-types";

interface ParsedColor {
  r: number; g: number; b: number; a: number;
}

function parseCssColor(input: string): ParsedColor | null {
  const value = input.trim();
  if (value.startsWith("#")) {
    const hex = value.slice(1);
    if (hex.length === 3) {
      return {
        r: parseInt(hex[0] + hex[0], 16), g: parseInt(hex[1] + hex[1], 16),
        b: parseInt(hex[2] + hex[2], 16), a: 1,
      };
    }
    if (hex.length === 6) {
      return {
        r: parseInt(hex.slice(0, 2), 16), g: parseInt(hex.slice(2, 4), 16),
        b: parseInt(hex.slice(4, 6), 16), a: 1,
      };
    }
    return null;
  }
  const match = value.match(/^rgba?\(([^)]+)\)$/i);
  if (!match) return null;
  const parts = match[1].split(",").map((p) => p.trim());
  if (parts.length < 3) return null;
  return {
    r: Math.min(255, parseFloat(parts[0])), g: Math.min(255, parseFloat(parts[1])),
    b: Math.min(255, parseFloat(parts[2])), a: Math.min(1, parseFloat(parts[3] ?? "1")),
  };
}

function withAlpha(input: string, alpha: number): string {
  const c = parseCssColor(input);
  if (!c) return input;
  return `rgba(${Math.round(c.r)}, ${Math.round(c.g)}, ${Math.round(c.b)}, ${Math.min(1, alpha).toFixed(3)})`;
}

function getTextStyle(d: DanDecoration): React.CSSProperties {
  if (d.glow_intensity === "none") return { color: d.color };
  return {
    color: "#ffffff",
    textShadow: ["0 1px 2px rgba(15,23,42,0.46)", `0 0 0.16em ${withAlpha("#ffffff", 0.84)}`].join(", "),
  };
}

function getGlowLayerStyle(d: DanDecoration): React.CSSProperties {
  if (d.glow_intensity === "none") return { color: d.color };
  if (d.glow_intensity === "subtle") {
    return {
      color: withAlpha("#ffffff", 0.24),
      textShadow: [
        `0 0 0.18em ${withAlpha("#ffffff", 0.88)}`, `0 0 0.34em ${withAlpha(d.color, 0.9)}`,
        `0 0 0.62em ${withAlpha(d.color, 0.64)}`, `0 0 0.94em ${withAlpha(d.color, 0.3)}`,
      ].join(", "),
      filter: [`drop-shadow(0 0 0.16em ${withAlpha(d.color, 0.72)})`, `drop-shadow(0 0 0.42em ${withAlpha(d.color, 0.4)})`].join(" "),
    };
  }
  return {
    color: withAlpha("#ffffff", 0.34),
    textShadow: [
      `0 0 0.24em ${withAlpha("#ffffff", 1)}`, `0 0 0.42em ${withAlpha(d.color, 1)}`,
      `0 0 0.74em ${withAlpha(d.color, 0.82)}`, `0 0 1.08em ${withAlpha(d.color, 0.44)}`,
    ].join(", "),
    filter: [
      `drop-shadow(0 0 0.18em ${withAlpha(d.color, 0.84)})`, `drop-shadow(0 0 0.5em ${withAlpha(d.color, 0.58)})`,
      `drop-shadow(0 0 0.9em ${withAlpha(d.color, 0.24)})`,
    ].join(" "),
  };
}

interface DecoratedBadgeProps {
  text: string;
  decoration?: DanDecoration | null;
  className?: string;
}

/**
 * Renders arbitrary text with DanDecoration glow/color styling.
 * Same visual as DecoratedUsername but accepts any text (not just usernames).
 */
export function DecoratedBadge({ text, decoration, className }: DecoratedBadgeProps) {
  if (!decoration) {
    return <span className={className}>{text}</span>;
  }
  const glowCls = (className ?? "").replace(/\btruncate\b/g, "").trim();
  return (
    <span className="relative inline-block max-w-full align-middle overflow-visible">
      {decoration.glow_intensity !== "none" && (
        <span
          aria-hidden="true"
          className={cn(
            glowCls,
            "pointer-events-none absolute inset-0 z-0 select-none overflow-visible whitespace-nowrap",
          )}
          style={getGlowLayerStyle(decoration)}
        >
          {text}
        </span>
      )}
      <span className={cn(className, "relative z-10")} style={getTextStyle(decoration)}>
        {text}
      </span>
    </span>
  );
}
