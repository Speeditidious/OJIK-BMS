export type LanguageCode = "ko" | "en" | "ja";

export const SUPPORTED_LANGUAGES: LanguageCode[] = ["ko", "en", "ja"];
export const DEFAULT_LANGUAGE: LanguageCode = "ko";

export function normalizeLanguage(value: string | null | undefined): LanguageCode | null {
  if (!value) return null;
  const base = value.trim().toLowerCase().split(/[-_]/)[0];
  return SUPPORTED_LANGUAGES.includes(base as LanguageCode) ? (base as LanguageCode) : null;
}

export function detectInitialClientLanguage(
  savedLanguage: string | null | undefined,
  navigatorLanguage: string | null | undefined,
): LanguageCode {
  return normalizeLanguage(savedLanguage) ?? normalizeLanguage(navigatorLanguage) ?? DEFAULT_LANGUAGE;
}
