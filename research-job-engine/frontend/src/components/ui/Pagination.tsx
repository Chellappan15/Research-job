import { ChevronLeft, ChevronRight } from "lucide-react";

import { formatNumber } from "../../lib/format";

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  busy = false,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  busy?: boolean;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total === 0) return null;
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);
  const btn =
    "inline-flex items-center gap-1 rounded-md border border-line-strong bg-surface px-3 py-1.5 text-sm font-medium text-fg hover:bg-hover disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-surface";
  return (
    <nav
      aria-label="Pagination"
      className="flex flex-col items-center justify-between gap-3 sm:flex-row"
    >
      <p className="text-sm text-fg-muted tabular" aria-live="polite">
        Showing <span className="text-fg">{formatNumber(first)}</span>–
        <span className="text-fg">{formatNumber(last)}</span> of{" "}
        <span className="text-fg">{formatNumber(total)}</span>
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          className={btn}
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1 || busy}
          aria-label="Previous page"
        >
          <ChevronLeft className="size-4" aria-hidden /> Prev
        </button>
        <span className="px-1 text-sm text-fg-muted tabular">
          Page {formatNumber(Math.min(page, pages))} of {formatNumber(pages)}
        </span>
        <button
          type="button"
          className={btn}
          onClick={() => onPageChange(page + 1)}
          disabled={page >= pages || busy}
          aria-label="Next page"
        >
          Next <ChevronRight className="size-4" aria-hidden />
        </button>
      </div>
    </nav>
  );
}
