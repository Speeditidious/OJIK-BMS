import { toPng } from "html-to-image";

export interface CaptureOptions {
  backgroundColor?: string;
  pixelRatio?: number;
  /**
   * Predicate deciding whether a node is included in the capture. Defaults to
   * excluding any element marked with `data-export-exclude` (and its subtree) —
   * used for on-screen-only controls that must not appear in the saved image.
   */
  filter?: (node: HTMLElement) => boolean;
}

/** Default capture filter: drop `[data-export-exclude]` nodes and their subtrees. */
function defaultCaptureFilter(node: HTMLElement): boolean {
  return !(node instanceof HTMLElement && node.hasAttribute("data-export-exclude"));
}

/**
 * Captures a DOM node to a PNG data URL.
 * Tries pixelRatio 2 → 1.5 → 1 on canvas size errors.
 * Returns { dataUrl, pixelRatioUsed }.
 */
export async function captureNodeToPng(
  node: HTMLElement,
  opts: CaptureOptions = {},
): Promise<{ dataUrl: string; pixelRatioUsed: number }> {
  const backgroundColor = opts.backgroundColor ?? resolveBackground();
  const ratios = opts.pixelRatio != null ? [opts.pixelRatio] : [2, 1.5, 1];
  const filter = opts.filter ?? defaultCaptureFilter;

  for (const pixelRatio of ratios) {
    try {
      await document.fonts.ready;
      const dataUrl = await toPng(node, {
        backgroundColor,
        pixelRatio,
        cacheBust: true,
        fetchRequestInit: { mode: "cors" },
        imagePlaceholder: makeInitialPlaceholder(48),
        filter,
      });
      return { dataUrl, pixelRatioUsed: pixelRatio };
    } catch (err) {
      const isLast = pixelRatio === ratios[ratios.length - 1];
      if (isLast) throw err;
      // silently retry with lower ratio
    }
  }
  throw new Error("captureNodeToPng: all pixel ratios failed");
}

function resolveBackground(): string {
  if (typeof window === "undefined") return "#12151C";
  const bg = getComputedStyle(document.documentElement)
    .getPropertyValue("--background")
    .trim();
  return bg ? `hsl(${bg})` : "#12151C";
}

/** 1×1 transparent PNG as base64 placeholder for cross-origin images. */
function makeInitialPlaceholder(size: number): string {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = "hsl(var(--muted) / 0.4)";
    ctx.fillRect(0, 0, size, size);
  }
  return canvas.toDataURL();
}
