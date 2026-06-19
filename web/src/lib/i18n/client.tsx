"use client";

import i18next from "i18next";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { I18nextProvider, initReactI18next } from "react-i18next";

import {
  AUTO_LANGUAGE_COOKIE,
  DEFAULT_LANGUAGE,
  MANUAL_LANGUAGE_COOKIE,
  detectNavigatorLanguage,
  normalizeLanguage,
  type LanguageCode,
} from "./languages";
import { resources } from "./resources";

const LANGUAGE_STORAGE_KEY = "ojikbms:language";

interface LanguageContextValue {
  language: LanguageCode;
  setLanguage: (language: LanguageCode) => void;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

let initialized = false;

function ensureI18nInitialized(language: LanguageCode) {
  if (initialized) {
    return;
  }

  initialized = true;
  void i18next.use(initReactI18next).init({
    resources,
    lng: language,
    fallbackLng: DEFAULT_LANGUAGE,
    interpolation: {
      escapeValue: false,
    },
  });
}

function readCookie(name: string): string | null {
  const prefix = `${name}=`;
  return (
    document.cookie
      .split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith(prefix))
      ?.slice(prefix.length) ?? null
  );
}

function writeLanguageCookie(name: string, language: LanguageCode) {
  document.cookie = `${name}=${language}; path=/; max-age=31536000; samesite=lax`;
}

function detectInitialLanguage(): LanguageCode {
  if (typeof window === "undefined") return DEFAULT_LANGUAGE;

  const stored = normalizeLanguage(window.localStorage.getItem(LANGUAGE_STORAGE_KEY));
  const manualCookie = normalizeLanguage(readCookie(MANUAL_LANGUAGE_COOKIE));
  const autoCookie = normalizeLanguage(readCookie(AUTO_LANGUAGE_COOKIE));
  const navigatorLanguage = detectNavigatorLanguage(
    Array.isArray(navigator.languages) && navigator.languages.length > 0
      ? navigator.languages
      : [navigator.language],
  );

  if (!stored && !manualCookie && !autoCookie && navigatorLanguage) {
    writeLanguageCookie(AUTO_LANGUAGE_COOKIE, navigatorLanguage);
  }

  return stored ?? manualCookie ?? autoCookie ?? navigatorLanguage ?? DEFAULT_LANGUAGE;
}

export function I18nProvider({
  children,
  initialLanguage,
}: {
  children: React.ReactNode;
  initialLanguage: LanguageCode;
}) {
  const [language, setLanguageState] = useState<LanguageCode>(initialLanguage);

  ensureI18nInitialized(language);

  useEffect(() => {
    const browserLanguage = detectInitialLanguage();
    if (browserLanguage !== language) {
      // Hydration-safe: server renders with `initialLanguage`; after mount we
      // reconcile with client-only sources (localStorage) that the server
      // cannot read. This is the canonical use of effect-driven setState.
      setLanguageState(browserLanguage);
    }
    // Intentionally run once on mount — `language` only matters for the
    // initial reconciliation; subsequent changes go through `setLanguage`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (i18next.language !== language) {
      void i18next.changeLanguage(language);
    }
  }, [language]);

  const value = useMemo<LanguageContextValue>(
    () => ({
      language,
      setLanguage: (nextLanguage) => {
        setLanguageState(nextLanguage);
        window.localStorage.setItem(LANGUAGE_STORAGE_KEY, nextLanguage);
        writeLanguageCookie(MANUAL_LANGUAGE_COOKIE, nextLanguage);
      },
    }),
    [language],
  );

  return (
    <LanguageContext.Provider value={value}>
      <I18nextProvider i18n={i18next}>{children}</I18nextProvider>
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used within I18nProvider");
  }
  return context;
}
