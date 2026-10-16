"use client";

import { useState } from "react";
import {
  CheckCircleIcon,
  ChevronDownIcon,
  FileIcon,
  FolderIcon,
  RefreshIcon,
} from "../icons";
import { INITIAL_DOCUMENTS, TOTAL_DOCUMENTS, USER_ROLES } from "./data";

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const CATEGORY_TONES = {
  HR: "bg-violet-50 text-violet-600",
  Engineering: "bg-sky-50 text-sky-600",
  Security: "bg-emerald-50 text-emerald-600",
  General: "bg-slate-100 text-slate-600",
};

const COLUMNS = [
  { label: "Document Title", className: "" },
  { label: "Category", className: "" },
  { label: "Last Update", className: "" },
  { label: "Allowed Users", className: "" },
  { label: "Actions", className: "text-right" },
];

function RoleTag({ children }) {
  return (
    <span className="inline-block rounded-full bg-indigo-50 px-2.5 py-1 text-[11px] font-medium text-indigo-700">
      {children}
    </span>
  );
}

// Multi-select with removable chips, similar to the "Select Multiple Agents" reference.
// The option list opens inline (not as a popover) so the table's scroll area never clips it.
function RoleSelect({ value, onChange }) {
  const [open, setOpen] = useState(false);

  const toggle = (role) =>
    onChange(value.includes(role) ? value.filter((r) => r !== role) : [...value, role]);

  return (
    <div className="w-72 rounded-lg border border-slate-300 bg-white p-2">
      {value.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {value.map((role) => (
            <span
              key={role}
              className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white py-1 pl-3 pr-2 text-xs text-slate-800"
            >
              {role}
              <button
                type="button"
                onClick={() => toggle(role)}
                aria-label={`Remove ${role}`}
                className="rounded-full p-0.5 text-slate-500 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
              >
                <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                  <path d="M6 6l12 12M18 6 6 18" />
                </svg>
              </button>
            </span>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between border-b border-slate-300 pb-1.5 text-left text-xs text-slate-400 transition hover:text-slate-600 focus:outline-none focus-visible:border-indigo-500"
      >
        Select multiple user roles
        <ChevronDownIcon className={`h-4 w-4 transition ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <ul className="mt-2 max-h-40 overflow-y-auto">
          {USER_ROLES.map((role) => (
            <li key={role}>
              <label className="flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-sm text-slate-700 hover:bg-slate-50">
                <input
                  type="checkbox"
                  checked={value.includes(role)}
                  onChange={() => toggle(role)}
                  className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                />
                {role}
              </label>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const linkBtn =
  "rounded text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500";

export default function DocumentsManager() {
  const [docs, setDocs] = useState(INITIAL_DOCUMENTS);
  // drafts[id] exists only while that row is being edited
  const [drafts, setDrafts] = useState({});

  const [path, setPath] = useState("");
  const [pathError, setPathError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submittedPath, setSubmittedPath] = useState("");

  const handlePathSubmit = async (e) => {
    e.preventDefault();
    const value = path.trim();
    setSubmittedPath("");

    if (!value) {
      setPathError("Enter the folder path.");
      return;
    }
    setPathError("");
    setSubmitting(true);

    // TODO: send `value` to your backend to start indexing, e.g.
    // await fetch("/api/admin/documents/folder", { method: "POST", body: JSON.stringify({ path: value }) });
    await wait(1200);

    setSubmitting(false);
    setSubmittedPath(value);
    setPath("");
  };

  const startEdit = (doc) => setDrafts((prev) => ({ ...prev, [doc.id]: [...doc.roles] }));

  const setDraft = (id, roles) => setDrafts((prev) => ({ ...prev, [id]: roles }));

  const submitRoles = (id) => {
    // TODO: save drafts[id] to your backend (e.g. PATCH /api/admin/documents/:id)
    setDocs((prev) => prev.map((d) => (d.id === id ? { ...d, roles: drafts[id] } : d)));
    setDrafts((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  };

  return (
    <div className="space-y-8">
      {/* Title row */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Corporate Documents &amp; RAG Validation
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Index corporate knowledge bases from a folder and control which user roles can access each document.
        </p>
      </div>

      {/* Folder path */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <form onSubmit={handlePathSubmit} noValidate>
          <label htmlFor="folder-path" className="block text-base font-semibold text-slate-900">
            Document Folder Path
          </label>
          <p className="mt-1 text-sm text-slate-500">
            Enter the path to the folder that contains the documents to index.
          </p>

          <div className="mt-4 flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <FolderIcon className="pointer-events-none absolute left-4 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-slate-400" />
              <input
                id="folder-path"
                type="text"
                value={path}
                onChange={(e) => setPath(e.target.value)}
                placeholder="/mnt/company-docs/hr-policies"
                aria-invalid={!!pathError}
                className={`block w-full rounded-xl border bg-slate-50 py-3 pl-11 pr-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:bg-white focus:ring-4 ${
                  pathError
                    ? "border-red-300 focus:border-red-500 focus:ring-red-100"
                    : "border-slate-200 focus:border-indigo-500 focus:ring-indigo-100"
                }`}
              />
            </div>
            <button
              type="submit"
              disabled={submitting}
              className="flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-200 transition hover:bg-indigo-700 focus:outline-none focus-visible:ring-4 focus-visible:ring-indigo-200 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {submitting && <RefreshIcon className="h-4 w-4 animate-spin" />}
              {submitting ? "Submitting..." : "Submit"}
            </button>
          </div>

          {pathError && (
            <p role="alert" className="mt-2 text-sm text-red-600">
              {pathError}
            </p>
          )}
          {submittedPath && (
            <p role="status" className="mt-3 flex items-center gap-1.5 text-sm text-emerald-600">
              <CheckCircleIcon className="h-4 w-4 shrink-0" />
              <span className="break-all">Folder submitted for indexing: {submittedPath}</span>
            </p>
          )}
        </form>
      </section>

      {/* Table */}
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between gap-4 px-6 py-5">
          <h2 className="text-base font-semibold text-slate-900">Ingested Document Knowledge States</h2>
          <p className="shrink-0 text-sm text-slate-400">Showing all {TOTAL_DOCUMENTS} documents</p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[1000px] text-left">
            <thead>
              <tr className="border-y border-slate-200 bg-slate-50">
                {COLUMNS.map((c) => (
                  <th
                    key={c.label}
                    scope="col"
                    className={`px-6 py-3.5 text-xs font-semibold uppercase tracking-wider text-slate-500 ${c.className}`}
                  >
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {docs.length === 0 && (
                <tr>
                  <td colSpan={COLUMNS.length} className="px-6 py-10 text-center text-sm text-slate-400">
                    No documents yet. Submit a folder path to get started.
                  </td>
                </tr>
              )}
              {docs.map((d) => {
                const draft = drafts[d.id];
                const editing = draft !== undefined;
                return (
                  <tr key={d.id} className="transition hover:bg-slate-50/60">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3 text-sm font-medium text-slate-800">
                        <FileIcon className="h-[18px] w-[18px] shrink-0 text-red-500" />
                        {d.title}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-block rounded-full px-2.5 py-1 text-[11px] font-medium ${CATEGORY_TONES[d.category] ?? CATEGORY_TONES.General}`}>
                        {d.category}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-400">{d.updated}</td>
                    <td className="px-6 py-4">
                      {editing ? (
                        <RoleSelect value={draft} onChange={(roles) => setDraft(d.id, roles)} />
                      ) : d.roles.length > 0 ? (
                        <div className="flex max-w-xs flex-wrap gap-1.5">
                          {d.roles.map((r) => (
                            <RoleTag key={r}>{r}</RoleTag>
                          ))}
                        </div>
                      ) : (
                        <span className="text-sm text-slate-400">No roles assigned</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-4">
                        <button
                          type="button"
                          disabled
                          title="Preview is not available yet"
                          className={`${linkBtn} cursor-not-allowed text-slate-300`}
                        >
                          Preview
                        </button>
                        <button
                          type="button"
                          onClick={() => startEdit(d)}
                          disabled={editing}
                          className={`${linkBtn} text-indigo-600 hover:text-indigo-700 disabled:cursor-not-allowed disabled:text-slate-300 disabled:hover:text-slate-300`}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => submitRoles(d.id)}
                          disabled={!editing}
                          className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white transition hover:bg-indigo-700 focus:outline-none focus-visible:ring-4 focus-visible:ring-indigo-200 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                        >
                          Submit
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}