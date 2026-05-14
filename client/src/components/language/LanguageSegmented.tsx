import { useTranslation } from "react-i18next";

import type { LanguageCode } from "../../types";

const LANGUAGES: LanguageCode[] = ["ko", "en", "ja"];

export function LanguageSegmented({
  value,
  onChange,
}: {
  value: LanguageCode;
  onChange: (language: LanguageCode) => void;
}) {
  const { t } = useTranslation();

  return (
    <div
      className="language-segmented"
      role="radiogroup"
      aria-label={t("common.language.label")}
    >
      {LANGUAGES.map((language) => {
        const selected = language === value;
        return (
          <button
            key={language}
            type="button"
            role="radio"
            aria-checked={selected}
            className={`language-segmented-option${selected ? " is-active" : ""}`}
            onClick={() => onChange(language)}
          >
            {t(`common.language.${language}`)}
          </button>
        );
      })}
    </div>
  );
}
