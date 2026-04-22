"use client";

import { useBmsforceEmblems } from "./RankingDisplayConfigProvider";
import { resolveEmblem, emblemStyle } from "@/lib/bmsforce-emblem";

interface BmsforceValueProps {
  value: number | null | undefined;
  className?: string;
  /**
   * true (default): apply tier color + glow decoration.
   * false: render plain formatted number only.
   */
  decorate?: boolean;
}

/**
 * Renders a BMSFORCE value (3 decimal places) with optional tier-based
 * color and glow decoration sourced from RankingDisplayConfigProvider.
 *
 * Loading: while emblems are not yet resolved, renders plain text (no flicker).
 */
export function BmsforceValue({ value, className, decorate = true }: BmsforceValueProps) {
  const emblems = useBmsforceEmblems();

  if (!Number.isFinite(value ?? NaN)) {
    return <span className={className}>-</span>;
  }

  const v = value as number;
  const text = v.toFixed(3);

  if (!decorate || emblems.length === 0) {
    return <span className={className}>{text}</span>;
  }

  const emblem = resolveEmblem(v, emblems);
  if (!emblem) {
    return <span className={className}>{text}</span>;
  }

  return (
    <span
      className={className}
      style={emblemStyle(emblem)}
      aria-label={emblem.label ? `BMSFORCE ${text} (${emblem.label})` : undefined}
    >
      {text}
    </span>
  );
}
