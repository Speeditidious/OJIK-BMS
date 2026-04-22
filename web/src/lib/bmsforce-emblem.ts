import type React from "react";

/** Supported glow intensities for BMSFORCE emblems. */
export type GlowIntensity = "none" | "subtle" | "strong";

/** A single BMSFORCE tier emblem, as returned by GET /rankings/display-config. */
export interface BmsforceEmblem {
  tier: string;
  min_value: number;
  max_value: number | null;
  color: string;            // "#RRGGBB"
  glow_intensity: GlowIntensity;
  label?: string | null;
}

/** Full response from GET /rankings/display-config. */
export interface RankingDisplayConfig {
  bmsforce_emblems: BmsforceEmblem[];
}

/**
 * Resolve which emblem applies for a given BMSFORCE value.
 * Assumes emblems are sorted by min_value ascending.
 * O(N), N ≤ 20.
 */
export function resolveEmblem(
  value: number,
  emblems: BmsforceEmblem[],
): BmsforceEmblem | null {
  if (emblems.length === 0) return null;
  // Find the last emblem whose min_value <= value
  let match: BmsforceEmblem | null = null;
  for (const emblem of emblems) {
    if (value >= emblem.min_value) {
      match = emblem;
    } else {
      break;
    }
  }
  if (!match) return null;
  // Check max_value bound
  if (match.max_value !== null && value > match.max_value) return null;
  return match;
}

/**
 * Convert a BmsforceEmblem to a React inline style for text decoration.
 * Applies color and glow based on glow_intensity.
 */
export function emblemStyle(emblem: BmsforceEmblem | null): React.CSSProperties {
  if (!emblem) return {};
  const base: React.CSSProperties = { color: emblem.color };
  if (emblem.glow_intensity === "subtle") {
    base.textShadow = `0 0 6px ${emblem.color}55`;
  } else if (emblem.glow_intensity === "strong") {
    base.textShadow = `0 0 8px ${emblem.color}88, 0 0 14px ${emblem.color}44`;
    base.fontWeight = 700;
  }
  return base;
}
