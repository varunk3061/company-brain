"use client";

import { useEffect, useState } from "react";
import { Search, X } from "lucide-react";
import Badge from "@/components/ui/Badge";
import { getAuditLogs } from "@/services/auditService";
import { actionLabel, displayName, formatDate, formatDateTime, formatTime } from "@/lib/format";

const COLUMNS = ["Time", "Actor", "Action", "Target"];

// Each kind of action gets its own colour, using the existing theme tokens only.
// Exact actions first, then the verb at the end of the action ("user.create" -> "create").
const ACTION_TONE = {
  "document.access.update": "warning",
  "document.view": "neutral",
  "rag.ask": "cat-2",
};

const VERB_TONE = {
  create: "success",
  upload: "brand",
  update: "info",
  delete: "danger",
};

const actionTone = (action = "") =>
  ACTION_TONE[action] ?? VERB_TONE[String(action).split(".").pop()] ?? "neutral";

const inputCls =
  "block w-full rounded-control border border-line bg-surface-2 py-2.5 text-sm text-ink outline-none transition placeholder:text-ink-3 focus:border-brand focus:bg-surface focus:ring-4 focus:ring-brand/25";

export default function AuditLogs() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);

  // Filters: the actor text is debounced so typing does not fire a request per key.
  const [actorInput, setActorInput] = useState("");
  const [actor, setActor] = useState("");
  const [action, setAction] = useState("");
  const [actions, setActions] = useState([]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setActor(actorInput.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [actorInput]);

  useEffect(() => {
    let active = true;

    getAuditLogs(page, 25, { action, actor })
      .then((result) => {
        if (active) {
          setData(result);
          setError("");
          if (Array.isArray(result.actions)) setActions(result.actions);
        }
      })
      .catch((err) => {
        if (active) setError(err.message || "Unable to load audit logs.");
      });

    return () => {
      active = false;
    };
  }, [page, action, actor]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const filtering = Boolean(action || actor);

  const clearFilters = () => {
    setActorInput("");
    setActor("");
    setAction("");
    setPage(1);
  };

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
        {/* Filters */}
        <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center">
          <div className="relative w-full sm:max-w-xs">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
            <input
              type="search"
              value={actorInput}
              onChange={(event) => setActorInput(event.target.value)}
              placeholder="Search by actor name or email..."
              aria-label="Filter by actor"
              className={`${inputCls} pl-10 pr-4`}
            />
          </div>

          <select
            value={action}
            onChange={(event) => {
              setAction(event.target.value);
              setPage(1);
            }}
            aria-label="Filter by action"
            className={`${inputCls} px-4 sm:w-56`}
          >
            <option value="">All actions</option>
            {actions.map((value) => (
              <option key={value} value={value}>
                {actionLabel(value)}
              </option>
            ))}
          </select>

          {filtering && (
            <button
              type="button"
              onClick={clearFilters}
              className="inline-flex items-center gap-1.5 self-start rounded-control px-3 py-2 text-sm font-medium text-ink-3 transition hover:bg-surface-3 hover:text-ink sm:self-auto"
            >
              <X className="h-4 w-4" aria-hidden="true" />
              Clear filters
            </button>
          )}
        </div>

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
                    {filtering ? "No audit entries match these filters." : "No audit entries yet."}
                  </td>
                </tr>
              )}
              {data?.items.map((row, index) => (
                <tr key={`${row.ts}-${index}`} className="transition hover:bg-surface-2/60">
                  <td className="whitespace-nowrap px-6 py-4" title={formatDateTime(row.ts)}>
                    <span className="block text-sm text-ink-2">{formatDate(row.ts)}</span>
                    <span className="block text-xs text-ink-3">{formatTime(row.ts)}</span>
                  </td>
                  <td className="px-6 py-4 text-sm font-medium text-ink">{displayName(row.actor_name)}</td>
                  <td className="px-6 py-4">
                    <Badge tone={actionTone(row.action)}>{actionLabel(row.action)}</Badge>
                  </td>
                  <td className="max-w-xs truncate px-6 py-4 text-sm text-ink-2" title={row.target}>{row.target}</td>
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
