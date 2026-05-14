/**
 * Compute the canonical href for a song/fumen detail page.
 * Uses externally shareable hash routes:
 * - md5 if available → /songs/md5/{md5}
 * - else sha256 → /songs/sha256/{sha256}
 */
export function songHref(
  fumen: { fumen_id?: string | null; sha256?: string | null; md5?: string | null },
  userId?: string,
): string {
  let href: string | null = null;
  if (fumen.md5) href = `/songs/md5/${encodeURIComponent(fumen.md5)}`;
  else if (fumen.sha256) href = `/songs/sha256/${encodeURIComponent(fumen.sha256)}`;
  if (!href) throw new Error("songHref: fumen must have md5 or sha256");
  return userId ? `${href}?user_id=${encodeURIComponent(userId)}` : href;
}

/**
 * Parse a song detail route segment into a value the backend accepts.
 * Supports prefixed legacy segments (`md5=...`, `sha256=...`, `fumen_id=...`)
 * and raw-hash/UUID segments for backward compatibility.
 */
export function parseSongRouteSegment(segment: string): string {
  const decoded = decodeURIComponent(segment);
  const eq = decoded.indexOf("=");
  if (eq > 0) {
    const prefix = decoded.slice(0, eq);
    const value = decoded.slice(eq + 1);
    if (prefix === "md5" || prefix === "sha256" || prefix === "fumen" || prefix === "fumen_id") {
      return value;
    }
  }
  return decoded;
}
