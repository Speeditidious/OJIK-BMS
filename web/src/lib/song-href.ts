/**
 * Compute the canonical href for a song/fumen detail page.
 * Prefers sha256 over md5 to ensure LR2+Beatoraja records are both covered by the backend.
 */
export function songHref(fumen: { sha256?: string | null; md5?: string | null }): string {
  const hash = fumen.sha256 ?? fumen.md5;
  if (!hash) throw new Error("songHref: fumen must have sha256 or md5");
  return `/songs/${hash}`;
}
