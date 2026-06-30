export function getCaptureErrorMessage(error) {
  if (error instanceof Error && error.message) {
    return error.message;
  }

  const type = typeof error === "object" && error !== null ? error.type : null;
  if (type === "error" || type === "load") {
    const target = error.target || error.currentTarget || {};
    const src = target.currentSrc || target.src || target.href || "";
    return src
      ? `Image failed to load while generating the preview: ${src}`
      : "An image failed to load while generating the preview.";
  }

  const text = String(error);
  return text === "[object Event]"
    ? "An image failed to load while generating the preview."
    : text;
}
