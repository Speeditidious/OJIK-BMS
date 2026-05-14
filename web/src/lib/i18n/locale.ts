import type { LanguageCode } from "./languages";

const LOCALE_BY_LANGUAGE: Record<LanguageCode, string> = {
  ko: "ko-KR",
  en: "en-US",
  ja: "ja-JP",
};

export function localeFromLanguage(language: string | undefined | null): string {
  if (!language) return LOCALE_BY_LANGUAGE.ko;
  if (language.startsWith("ja")) return LOCALE_BY_LANGUAGE.ja;
  if (language.startsWith("en")) return LOCALE_BY_LANGUAGE.en;
  return LOCALE_BY_LANGUAGE.ko;
}
