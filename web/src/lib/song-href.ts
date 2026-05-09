/**
 * Compute the canonical href for a song/fumen detail page.
 * Prefers the server fumen_id; falls back to legacy hashes for older responses.
 */
export function songHref(fumen: { fumen_id?: string | null; sha256?: string | null; md5?: string | null }): string {
  const id = fumen.fumen_id ?? fumen.sha256 ?? fumen.md5;
  if (!id) throw new Error("songHref: fumen must have fumen_id, sha256, or md5");
  return `/songs/${id}`;
}
