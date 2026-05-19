"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  label?: string;
  placeholder?: string;
}

export function Pagination({
  page,
  totalPages,
  onPageChange,
  label,
  placeholder,
}: PaginationProps) {
  const safeTotal = Math.max(1, totalPages);
  const [value, setValue] = useState(String(page));

  useEffect(() => {
    setValue(String(page));
  }, [page]);

  const commit = () => {
    const parsed = Number.parseInt(value, 10);
    const next = Number.isFinite(parsed) ? Math.min(Math.max(parsed, 1), safeTotal) : page;
    setValue(String(next));
    onPageChange(next);
  };

  return (
    <div className="flex items-center justify-center gap-2">
      <Button
        variant="outline"
        size="sm"
        className="h-8 px-3"
        disabled={page <= 1}
        onClick={() => onPageChange(Math.max(1, page - 1))}
        aria-label="Previous page"
      >
        {"< Prev"}
      </Button>
      <span className="min-w-20 text-center text-label text-muted-foreground">
        {label ?? `${page} / ${safeTotal}`}
      </span>
      <Button
        variant="outline"
        size="sm"
        className="h-8 px-3"
        disabled={page >= safeTotal}
        onClick={() => onPageChange(Math.min(safeTotal, page + 1))}
        aria-label="Next page"
      >
        {"Next >"}
      </Button>
      <div className="ml-4 flex items-center gap-1">
        <Input
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") commit();
          }}
          inputMode="numeric"
          className="h-8 w-16 text-center"
          placeholder={placeholder}
        />
        <Button
          variant="outline"
          size="sm"
          className="h-8 px-3"
          onClick={commit}
        >
          이동
        </Button>
      </div>
    </div>
  );
}
