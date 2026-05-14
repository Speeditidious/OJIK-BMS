"use client";

import { Check, Globe } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useLanguage } from "@/lib/i18n/client";
import type { LanguageCode } from "@/lib/i18n/languages";
import { cn } from "@/lib/utils";

const LANGUAGES: LanguageCode[] = ["ko", "en", "ja"];

export function LanguageSwitcher({ className }: { className?: string }) {
  const { t } = useTranslation();
  const { language, setLanguage } = useLanguage();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={t("common.language.label")}
          className={cn(
            "rounded-md p-2 transition-colors cursor-pointer",
            className ?? "text-muted-foreground hover:text-foreground hover:bg-secondary",
          )}
        >
          <Globe className="h-5 w-5" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-40">
        {LANGUAGES.map((code) => {
          const selected = code === language;
          return (
            <DropdownMenuItem
              key={code}
              onSelect={() => setLanguage(code)}
              className="justify-between"
            >
              <span>{t(`common.language.${code}`)}</span>
              <Check
                className={cn("h-4 w-4", selected ? "opacity-100" : "opacity-0")}
                aria-hidden="true"
              />
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
