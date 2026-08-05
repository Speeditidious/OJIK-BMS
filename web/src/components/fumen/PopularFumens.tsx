"use client";

import { useState } from "react";
import { Flame } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { PopularFumensTable } from "@/components/fumen/PopularFumensTable";
import type { PopularRange } from "@/types";

export function PopularFumensDialog() {
  const { t } = useTranslation();
  // Mirrors PopularFumensTable's internal range state (via onRangeChange)
  // so the dialog title can keep showing the live selected range, exactly
  // as it did before the range/sortBy state moved into PopularFumensTable.
  const [range, setRange] = useState<PopularRange>("weekly");

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <Flame className="h-4 w-4 text-primary" />
          {t("songs.popular.button")}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Flame className="h-5 w-5 text-primary" />
            {t("songs.popular.title", { range: t(`songs.popular.range.${range}`) })}
          </DialogTitle>
        </DialogHeader>

        <PopularFumensTable onRangeChange={setRange} />
      </DialogContent>
    </Dialog>
  );
}
