export const SUPPORTED_LANGUAGES = ["ko", "en", "ja"];
export const DEFAULT_LANGUAGE = "ko";

export function normalizeLanguage(value) {
  if (!value || typeof value !== "string") return null;
  const base = value.trim().toLowerCase().split(/[-_]/)[0];
  return SUPPORTED_LANGUAGES.includes(base) ? base : null;
}

export function detectInitialClientLanguage(savedLanguage, navigatorLanguage) {
  return normalizeLanguage(savedLanguage) ?? normalizeLanguage(navigatorLanguage) ?? DEFAULT_LANGUAGE;
}
