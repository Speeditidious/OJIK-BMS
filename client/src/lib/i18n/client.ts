import i18next from "i18next";
import { initReactI18next } from "react-i18next";

import { DEFAULT_LANGUAGE, type LanguageCode } from "./languages";
import { resources } from "./resources";

let initialized = false;

export function initializeClientI18n(language: LanguageCode) {
  if (!initialized) {
    initialized = true;
    void i18next.use(initReactI18next).init({
      resources,
      lng: language,
      fallbackLng: DEFAULT_LANGUAGE,
      interpolation: {
        escapeValue: false,
      },
    });
    return;
  }

  if (i18next.language !== language) {
    void i18next.changeLanguage(language);
  }
}

export function changeClientLanguage(language: LanguageCode) {
  initializeClientI18n(language);
}
