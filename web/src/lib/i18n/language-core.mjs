export const SUPPORTED_LANGUAGES = ["ko", "en", "ja"];
export const DEFAULT_LANGUAGE = "ko";

export function normalizeLanguage(value) {
  if (!value || typeof value !== "string") return null;
  const base = value.trim().toLowerCase().split(/[-_]/)[0];
  return SUPPORTED_LANGUAGES.includes(base) ? base : null;
}

export function parseAcceptLanguage(header) {
  if (!header) return null;
  return header
    .split(",")
    .map((part, index) => {
      const [tag, ...params] = part.trim().split(";");
      const qParam = params.find((param) => param.trim().startsWith("q="));
      const q = qParam ? Number(qParam.trim().slice(2)) : 1;
      return {
        language: normalizeLanguage(tag),
        q: Number.isFinite(q) ? q : 0,
        index,
      };
    })
    .filter((entry) => entry.language)
    .sort((a, b) => b.q - a.q || a.index - b.index)[0]?.language ?? null;
}

export function detectNavigatorLanguage(languages) {
  if (!Array.isArray(languages)) return null;
  for (const language of languages) {
    const normalized = normalizeLanguage(language);
    if (normalized) return normalized;
  }
  return null;
}

export function languageFromCountry(country) {
  const normalized = typeof country === "string" ? country.trim().toUpperCase() : "";
  if (normalized === "KR") return "ko";
  if (normalized === "JP") return "ja";
  if (normalized) return "en";
  return null;
}

export function detectLanguageFromRequestParts(parts) {
  return (
    normalizeLanguage(parts.manualCookie) ??
    normalizeLanguage(parts.autoCookie) ??
    parseAcceptLanguage(parts.acceptLanguage) ??
    languageFromCountry(parts.country) ??
    DEFAULT_LANGUAGE
  );
}
