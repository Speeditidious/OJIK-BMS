import {
  DEFAULT_LANGUAGE as CORE_DEFAULT_LANGUAGE,
  SUPPORTED_LANGUAGES as CORE_SUPPORTED_LANGUAGES,
  detectLanguageFromRequestParts as coreDetectLanguageFromRequestParts,
  detectNavigatorLanguage as coreDetectNavigatorLanguage,
  languageFromCountry as coreLanguageFromCountry,
  normalizeLanguage as coreNormalizeLanguage,
  parseAcceptLanguage as coreParseAcceptLanguage,
} from "./language-core.mjs";

export type LanguageCode = "ko" | "en" | "ja";

export const MANUAL_LANGUAGE_COOKIE = "ojikbms_language";
export const AUTO_LANGUAGE_COOKIE = "ojikbms_auto_language";

export const DEFAULT_LANGUAGE = CORE_DEFAULT_LANGUAGE as LanguageCode;
export const SUPPORTED_LANGUAGES = CORE_SUPPORTED_LANGUAGES as LanguageCode[];

export interface RequestLanguageParts {
  manualCookie?: string | null;
  autoCookie?: string | null;
  acceptLanguage?: string | null;
  country?: string | null;
}

export function normalizeLanguage(value: string | null | undefined): LanguageCode | null {
  return coreNormalizeLanguage(value) as LanguageCode | null;
}

export function parseAcceptLanguage(header: string | null | undefined): LanguageCode | null {
  return coreParseAcceptLanguage(header) as LanguageCode | null;
}

export function detectNavigatorLanguage(languages: readonly string[] | null | undefined): LanguageCode | null {
  return coreDetectNavigatorLanguage(languages ? [...languages] : null) as LanguageCode | null;
}

export function languageFromCountry(country: string | null | undefined): LanguageCode | null {
  return coreLanguageFromCountry(country) as LanguageCode | null;
}

export function detectLanguageFromRequestParts(parts: RequestLanguageParts): LanguageCode {
  return coreDetectLanguageFromRequestParts(parts) as LanguageCode;
}
