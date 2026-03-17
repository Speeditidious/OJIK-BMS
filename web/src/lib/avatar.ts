const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Resolves an avatar URL.
 * Relative paths (e.g. /uploads/avatars/...) are prefixed with the API base URL.
 * Absolute URLs (Discord CDN, etc.) are returned as-is.
 */
export function resolveAvatarUrl(url: string): string {
  if (url.startsWith("/")) {
    return `${API_URL}${url}`;
  }
  return url;
}
