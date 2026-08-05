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
import type { PopularRange, PopularSortBy } from "@/types";

export function PopularFumensDialog() {
  const { t } = useTranslation();
  // range/sortBy are owned here (in PopularFumensDialog, which stays
  // mounted across the dialog's open/close cycle) rather than inside
  // PopularFumensTable, and passed down as controlled props. DialogContent
  // unmounts its subtree on close, so if PopularFumensTable owned this
  // state uncontrolled, every close->reopen would reset it back to the
  // defaults. Lifting it here also lets the title below stay in sync with
  // the live selected range with no extra effect/flicker.
  const [range, setRange] = useState<PopularRange>("weekly");
  const [sortBy, setSortBy] = useState<PopularSortBy>("players");

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

        <PopularFumensTable range={range} onRangeChange={setRange} sortBy={sortBy} onSortByChange={setSortBy} />
      </DialogContent>
    </Dialog>
  );
}
