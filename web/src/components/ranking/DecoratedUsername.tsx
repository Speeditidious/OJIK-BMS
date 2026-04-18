"use client";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { DanDecoration } from "@/lib/ranking-types";

interface DecoratedUsernameProps {
  username: string;
  danDecoration?: DanDecoration | null;
  className?: string;
}

interface ParsedColor {
  r: number;
  g: number;
  b: number;
  a: number;
}

function removeClassToken(className: string | undefined, token: string): string {
  if (!className) {
    return "";
  }

  return className
    .split(/\s+/)
    .filter((part) => part && part !== token)
    .join(" ");
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function parseCssColor(input: string): ParsedColor | null {
  const value = input.trim();

  if (value.startsWith("#")) {
    const hex = value.slice(1);
    if (hex.length === 3) {
      return {
        r: Number.parseInt(hex[0] + hex[0], 16),
        g: Number.parseInt(hex[1] + hex[1], 16),
        b: Number.parseInt(hex[2] + hex[2], 16),
        a: 1,
      };
    }

    if (hex.length === 6) {
      return {
        r: Number.parseInt(hex.slice(0, 2), 16),
        g: Number.parseInt(hex.slice(2, 4), 16),
        b: Number.parseInt(hex.slice(4, 6), 16),
        a: 1,
      };
    }

    return null;
  }

  const match = value.match(/^rgba?\(([^)]+)\)$/i);
  if (!match) {
    return null;
  }

  const parts = match[1].split(",").map((part) => part.trim());
  if (parts.length < 3) {
    return null;
  }

  return {
    r: clamp(Number.parseFloat(parts[0]), 0, 255),
    g: clamp(Number.parseFloat(parts[1]), 0, 255),
    b: clamp(Number.parseFloat(parts[2]), 0, 255),
    a: clamp(Number.parseFloat(parts[3] ?? "1"), 0, 1),
  };
}

function toRgbaString(color: ParsedColor): string {
  return `rgba(${Math.round(color.r)}, ${Math.round(color.g)}, ${Math.round(color.b)}, ${color.a.toFixed(3)})`;
}

function withAlpha(input: string, alpha: number): string {
  const parsed = parseCssColor(input);
  if (!parsed) {
    return input;
  }

  return toRgbaString({
    ...parsed,
    a: clamp(alpha, 0, 1),
  });
}

function getTextStyle(decoration: DanDecoration): React.CSSProperties {
  const { color, glow_intensity } = decoration;
  if (glow_intensity === "none") {
    return { color };
  }

  return {
    color: "#ffffff",
    textShadow: [
      "0 1px 2px rgba(15, 23, 42, 0.46)",
      `0 0 0.16em ${withAlpha("#ffffff", 0.84)}`,
    ].join(", "),
  };
}

function getGlowLayerStyle(decoration: DanDecoration): React.CSSProperties {
  const { color, glow_intensity } = decoration;

  if (glow_intensity === "none") {
    return {
      color,
    };
  }

  if (glow_intensity === "subtle") {
    return {
      color: withAlpha("#ffffff", 0.24),
      textShadow: [
        `0 0 0.18em ${withAlpha("#ffffff", 0.88)}`,
        `0 0 0.34em ${withAlpha(color, 0.9)}`,
        `0 0 0.62em ${withAlpha(color, 0.64)}`,
        `0 0 0.94em ${withAlpha(color, 0.3)}`,
      ].join(", "),
      filter: [
        `drop-shadow(0 0 0.16em ${withAlpha(color, 0.72)})`,
        `drop-shadow(0 0 0.42em ${withAlpha(color, 0.4)})`,
      ].join(" "),
    };
  }

  return {
    color: withAlpha("#ffffff", 0.34),
    textShadow: [
      `0 0 0.24em ${withAlpha("#ffffff", 1)}`,
      `0 0 0.42em ${withAlpha(color, 1)}`,
      `0 0 0.74em ${withAlpha(color, 0.82)}`,
      `0 0 1.08em ${withAlpha(color, 0.44)}`,
    ].join(", "),
    filter: [
      `drop-shadow(0 0 0.18em ${withAlpha(color, 0.84)})`,
      `drop-shadow(0 0 0.5em ${withAlpha(color, 0.58)})`,
      `drop-shadow(0 0 0.9em ${withAlpha(color, 0.24)})`,
    ].join(" "),
  };
}

export function DecoratedUsername({
  username,
  danDecoration,
  className,
}: DecoratedUsernameProps) {
  if (!danDecoration) {
    return <span className={className}>{username}</span>;
  }

  const glowClassName = removeClassToken(className, "truncate");

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="relative inline-block max-w-full align-bottom overflow-visible">
            {danDecoration.glow_intensity !== "none" && (
              <span
                aria-hidden="true"
                className={cn(
                  glowClassName,
                  "pointer-events-none absolute inset-0 z-0 select-none overflow-visible whitespace-nowrap",
                )}
                style={getGlowLayerStyle(danDecoration)}
              >
                {username}
              </span>
            )}
            <span
              className={cn(className, "relative z-10")}
              style={getTextStyle(danDecoration)}
            >
              {username}
            </span>
          </span>
        </TooltipTrigger>
        <TooltipContent side="bottom" align="center" sideOffset={4}>
          <p>{danDecoration.display_text}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
