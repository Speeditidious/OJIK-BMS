"use client";

interface NumberedPaginationProps {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
}

/**
 * Numbered pagination control: prev/next arrows plus up to 7 page buttons,
 * with the last page always reachable via a trailing "…" when there are more.
 * Originally the ranking page's inline block; extracted so every offset-paginated
 * table that wants ranking-page-style page numbers (as opposed to the
 * prev/next + jump-to-page `Pagination` component) renders one identical control.
 *
 * Always renders, even when there's only one page (arrows disabled, single
 * "1" button) — pagination stays visible instead of popping in/out as the
 * result set crosses a page boundary.
 */
export function NumberedPagination({ page, totalPages, onChange }: NumberedPaginationProps) {
  return (
    <div className="flex items-center justify-center gap-2 pt-2">
      <button
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
        className="px-3 py-1.5 rounded border border-border text-body disabled:opacity-40 hover:bg-secondary transition-colors"
      >
        ←
      </button>
      {Array.from({ length: Math.min(totalPages, 7) }).map((_, i) => {
        const p = i + 1;
        return (
          <button
            key={p}
            onClick={() => onChange(p)}
            className={`px-3 py-1.5 rounded border border-border text-body transition-colors ${
              p === page ? "bg-primary text-primary-foreground" : "hover:bg-secondary"
            }`}
          >
            {p}
          </button>
        );
      })}
      {totalPages > 7 && (
        <>
          <span className="text-muted-foreground">…</span>
          <button
            onClick={() => onChange(totalPages)}
            className={`px-3 py-1.5 rounded border border-border text-body transition-colors ${
              page === totalPages ? "bg-primary text-primary-foreground" : "hover:bg-secondary"
            }`}
          >
            {totalPages}
          </button>
        </>
      )}
      <button
        disabled={page >= totalPages}
        onClick={() => onChange(page + 1)}
        className="px-3 py-1.5 rounded border border-border text-body disabled:opacity-40 hover:bg-secondary transition-colors"
      >
        →
      </button>
    </div>
  );
}
