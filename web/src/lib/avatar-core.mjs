export function resolveAvatarUrlCore(url, apiUrl) {
  if (url.startsWith("/")) {
    return `${apiUrl}${url}`;
  }
  return url;
}

export function getAvatarFallbackInitial(label) {
  const trimmed = label.trim();
  return trimmed ? trimmed.charAt(0).toUpperCase() : "?";
}
