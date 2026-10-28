// Shared table footer: "Showing 1–8 of 23 users" + Previous / Next.
// Every admin table shows PAGE_SIZE rows per page.
export const PAGE_SIZE = 8;

const btnCls =
  "rounded-control border border-line px-3 py-1.5 font-medium text-ink-2 transition hover:bg-surface-3 disabled:opacity-50 disabled:hover:bg-transparent";

export default function Pagination({ page, pageSize = PAGE_SIZE, total, onPageChange, noun = "entries" }) {
  if (!total) return null;

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(total, page * pageSize);

  return (
    <div className="flex flex-col gap-3 border-t border-line px-6 py-3 text-sm text-ink-3 sm:flex-row sm:items-center sm:justify-between">
      <span className="tabular-nums">
        Showing {first}–{last} of {total} {noun}
      </span>
      <div className="flex items-center gap-3">
        <span className="tabular-nums">
          Page {page} of {totalPages}
        </span>
        <div className="flex gap-2">
          <button type="button" onClick={() => onPageChange(page - 1)} disabled={page <= 1} className={btnCls}>
            Previous
          </button>
          <button type="button" onClick={() => onPageChange(page + 1)} disabled={page >= totalPages} className={btnCls}>
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
