/**
 * Resolves a tag color value to badge CSS style values.
 *
 * Accepts three input forms:
 * - Semantic design system token (`primary` | `secondary` | `accent` | `muted` | `warning` | `destructive`)
 *   → mapped to `hsl(var(--token))` with alpha for background/border.
 * - Hex color string (`#rrggbb`) → reused as-is with `+22` (bg) / `+88` (border) alpha suffix.
 * - `null` / `undefined` / unrecognized → falls back to slug/name pattern matching, then a
 *   deterministic palette hashed off the slug (only if `fallbackSeed` provided).
 *
 * The `muted` token uses `--muted-foreground` for text since `--muted` is itself a
 * surface color and would be invisible on most backgrounds.
 */

const SEMANTIC_TOKENS = new Set([
  "primary",
  "secondary",
  "accent",
  "muted",
  "warning",
  "destructive",
]);

const TAG_SLUG_COLOR_PATTERNS: ReadonlyArray<readonly [RegExp, string]> = [
  [/bug|버그|error|오류/, "#ef4444"],
  [/suggest|건의|feature|request|제안/, "#3b82f6"],
  [/question|질문|help|도움/, "#f59e0b"],
  [/other|기타|etc/, "#6b7280"],
];

const TAG_COLOR_PALETTE = ["#8b5cf6", "#10b981", "#f97316", "#06b6d4"];

export interface TagBadgeStyle {
  background: string;
  border: string;
  text: string;
}

function hexStyle(hex: string): TagBadgeStyle {
  return {
    background: `${hex}22`,
    border: `${hex}88`,
    text: hex,
  };
}

function tokenStyle(token: string): TagBadgeStyle {
  const textVar =
    token === "muted" ? "hsl(var(--muted-foreground))" : `hsl(var(--${token}))`;
  return {
    background: `hsl(var(--${token}) / 0.15)`,
    border: `hsl(var(--${token}) / 0.55)`,
    text: textVar,
  };
}

function fallbackStyle(seed: { slug: string; name: string }): TagBadgeStyle {
  const haystack = `${seed.slug} ${seed.name}`.toLowerCase();
  for (const [pattern, color] of TAG_SLUG_COLOR_PATTERNS) {
    if (pattern.test(haystack)) return hexStyle(color);
  }
  let hash = 0;
  for (const c of seed.slug) hash = ((hash * 31) + c.charCodeAt(0)) & 0x7fffffff;
  return hexStyle(TAG_COLOR_PALETTE[hash % TAG_COLOR_PALETTE.length]);
}

export function resolveTagBadgeStyle(
  color: string | null | undefined,
  fallbackSeed?: { slug: string; name: string },
): TagBadgeStyle {
  if (color) {
    if (SEMANTIC_TOKENS.has(color)) return tokenStyle(color);
    if (color.startsWith("#")) return hexStyle(color);
  }
  if (fallbackSeed) return fallbackStyle(fallbackSeed);
  return tokenStyle("primary");
}
