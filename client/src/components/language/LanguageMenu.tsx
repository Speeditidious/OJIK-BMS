import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Globe } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { LanguageCode } from "../../types";
import { Button } from "../primitives/Button";

const LANGUAGES: LanguageCode[] = ["ko", "en", "ja"];

export function LanguageMenu({
  value,
  onChange,
}: {
  value: LanguageCode;
  onChange: (language: LanguageCode) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const handleSelect = (language: LanguageCode) => {
    onChange(language);
    setOpen(false);
  };

  return (
    <div className="language-menu" ref={rootRef}>
      <Button
        variant="ghost"
        size="sm"
        leadingIcon={<Globe size={15} aria-hidden="true" />}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={t("common.language.label")}
        onClick={() => setOpen((current) => !current)}
      >
        <span>{t(`common.language.${value}`)}</span>
        <ChevronDown size={13} aria-hidden="true" className="language-menu-chevron" />
      </Button>
      {open ? (
        <ul className="language-menu-panel" role="listbox">
          {LANGUAGES.map((language) => {
            const selected = language === value;
            return (
              <li key={language}>
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className="language-menu-item"
                  onClick={() => handleSelect(language)}
                >
                  <span>{t(`common.language.${language}`)}</span>
                  {selected ? <Check size={14} aria-hidden="true" /> : null}
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
