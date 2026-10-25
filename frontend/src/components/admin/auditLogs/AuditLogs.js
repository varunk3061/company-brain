"use client";

import { useEffect, useState } from "react";
import Badge from "@/components/ui/Badge";
import { getAuditLogs } from "@/services/auditService";
import { actionLabel, displayName } from "@/lib/format";

const COLUMNS = ["Time", "Actor", "Action", "Target"];

const formatTime = (value) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "-" : date.toLocaleString();
};

export default function AuditLogs() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    let active = true;

    getAuditLogs(page)
      .then((result) => {
        if (active) {
          setData(result);
          setError("");
        }
      })
      .catch((err) => {
        if (active) setError(err.message || "Unable to load audit logs.");
      });

    return () => {
      active = false;
    };
  }, [page]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink">Audit Logs</h1>
        <p className="mt-1 text-sm text-ink-3">
          Changes made by administrators: users, organisation and document access. Question
          history will appear here once question answering is available.
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded-control border border-danger/30 bg-danger-soft p-4 text-sm text-danger">
          {error}
        </p>
      )}

      <section className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
        <div className="overflow-x-auto">
          <table className="w-full min-w-175 text-left">
            <thead>
              <tr className="border-y border-line bg-surface-2">
                {COLUMNS.map((column) => (
                  <th key={column} scope="col" className="px-6 py-3.5 text-xs font-semibold uppercase tracking-wider text-ink-3">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {!data && !error && (
                <tr>
                  <td colSpan={COLUMNS.length} className="px-6 py-10 text-center text-sm text-ink-3">
                    Loading audit logs…
                  </td>
                </tr>
              )}
              {data?.items.length === 0 && (
                <tr>
                  <td colSpan={COLUMNS.length} className="px-6 py-10 text-center text-sm text-ink-3">
                    No audit entries yet.
                  </td>
                </tr>
              )}
              {data?.items.map((row, index) => (
                <tr key={`${row.ts}-${index}`} className="transition hover:bg-surface-2/60">
                  <td className="px-6 py-4 text-sm text-ink-3">{formatTime(row.ts)}</td>
                  <td className="px-6 py-4 text-sm font-medium text-ink">{displayName(row.actor_name)}</td>
                  <td className="px-6 py-4">
                    <Badge tone="brand">{actionLabel(row.action)}</Badge>
                  </td>
                  <td className="max-w-xs truncate px-6 py-4 text-sm text-ink-2">{row.target}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {data && data.total > data.page_size && (
          <div className="flex items-center justify-between border-t border-line px-6 py-3 text-sm text-ink-3">
            <span>
              Page {data.page} of {totalPages} · {data.total} entries
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="rounded-control border border-line px-3 py-1.5 font-medium text-ink-2 hover:bg-surface-3 disabled:opacity-50"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="rounded-control border border-line px-3 py-1.5 font-medium text-ink-2 hover:bg-surface-3 disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
