"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CheckCircleIcon,
  ChevronDownIcon,
  FileIcon,
  FolderIcon,
  RefreshIcon,
} from "../icons";
import { INITIAL_DOCUMENTS, TOTAL_DOCUMENTS, USER_ROLES } from "./data";
import {
  scanFolder,
  getDocuments,
  updateDocumentPermissions,
  deleteDocument,
} from "@/services/documentService";

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
    onChange(
      value.includes(role) ? value.filter((r) => r !== role) : [...value, role],
    );

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
                <svg
                  viewBox="0 0 24 24"
                  className="h-3 w-3"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  aria-hidden="true"
                >
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
        <ChevronDownIcon
          className={`h-4 w-4 transition ${open ? "rotate-180" : ""}`}
        />
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
  const [docs, setDocs] = useState([]);
  // drafts[id] exists only while that row is being edited
  const [drafts, setDrafts] = useState({});
  // for edit modal
  const [selectedDoc, setSelectedDoc] = useState(null);

  const [path, setPath] = useState("");
  const [pathError, setPathError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submittedPath, setSubmittedPath] = useState("");

  // Document selected for deletion
  const [deleteDoc, setDeleteDoc] = useState(null);

  // Tracks whether the delete API request is running
  const [deleting, setDeleting] = useState(false);

  // Error message shown inside the delete modal
  const [deleteError, setDeleteError] = useState("");

  const loadDocuments = useCallback(async () => {
    try {
      const result = await getDocuments();
      // Map backend fields to the table row schema
      setDocs(
        result.map((d) => ({
          id: d.document_uuid,
          title: d.document_name,
          category: d.category || "General",
          updated: new Date(d.last_update).toLocaleDateString(),
          roles: d.allowed_roles || [],
        })),
      );
    } catch (err) {
      setPathError(err.message || "Failed to load documents.");
    }
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // Open the delete confirmation modal
  const openDeleteModal = (doc) => {
    setDeleteDoc(doc);
    setDeleteError("");
  };

  // Close the delete confirmation modal
  const closeDeleteModal = () => {
    if (deleting) return;

    setDeleteDoc(null);
    setDeleteError("");
  };

  // Delete the document after confirmation
  const handleDelete = async () => {
    if (!deleteDoc) return;

    setDeleting(true);
    setDeleteError("");

    try {
      // Call the backend delete API
      await deleteDocument(deleteDoc.id);

      // Remove the deleted document from the table
      setDocs((prev) => prev.filter((d) => d.id !== deleteDoc.id));

      // Close the modal after successful deletion
      setDeleteDoc(null);
    } catch (err) {
      // Display the error inside the modal
      setDeleteError(err.message || "Failed to delete document.");
    } finally {
      setDeleting(false);
    }
  };

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

    try {
      const result = await scanFolder(value);
      await loadDocuments();
      setSubmittedPath(
        `Scanned successfully: ${result.created_count} new, ${result.existing_count} existing.`,
      );
      setPath("");
    } catch (err) {
      setPathError(err.message || "Failed to scan folder.");
    } finally {
      setSubmitting(false);
    }
  };

  const startEdit = (doc) => {
    setDrafts((prev) => ({ ...prev, [doc.id]: [...doc.roles] }));
    setSelectedDoc(doc);
  };

  const closeModal = () => {
    if (selectedDoc) {
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[selectedDoc.id];
        return next;
      });
    }

    setSelectedDoc(null);
  };

  const setDraft = (id, roles) =>
    setDrafts((prev) => ({ ...prev, [id]: roles }));

  const submitRoles = async (id) => {
    try {
      await updateDocumentPermissions(id, drafts[id] || []);
      setDocs((prev) =>
        prev.map((d) => (d.id === id ? { ...d, roles: drafts[id] } : d)),
      );
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    } catch (err) {
      alert(err.message || "Failed to update permissions.");
    }
  };

  return (
    <div className="space-y-8">
      {/* Title row */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Corporate Documents &amp; RAG Validation
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Index corporate knowledge bases from a folder and control which user
          roles can access each document.
        </p>
      </div>

      {/* Folder path */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <form onSubmit={handlePathSubmit} noValidate>
          <label
            htmlFor="folder-path"
            className="block text-base font-semibold text-slate-900"
          >
            Document Folder Path
          </label>
          <p className="mt-1 text-sm text-slate-500">
            Enter the path to the folder that contains the documents to index.
          </p>

          <div className="mt-4 flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <FolderIcon className="pointer-events-none absolute left-4 top-1/2 h-4.5 w-4.5 -translate-y-1/2 text-slate-400" />
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
              className="flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-200 transition hover:bg-indigo-700 focus:outline-none focus-visible:ring-4 focus-visible:ring-indigo-200 disabled:cursor-not-allowed disabled:opacity-70 cursor-pointer"
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
            <p
              role="status"
              className="mt-3 flex items-center gap-1.5 text-sm text-emerald-600"
            >
              <CheckCircleIcon className="h-4 w-4 shrink-0" />
              <span className="break-all">
                Folder submitted for indexing: {submittedPath}
              </span>
            </p>
          )}
        </form>
      </section>

      {/* Table */}
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between gap-4 px-6 py-5">
          <h2 className="text-base font-semibold text-slate-900">
            Ingested Document Knowledge States
          </h2>
          <p className="shrink-0 text-sm text-slate-400">
            Showing all {docs.length} documents
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-250 text-left">
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
                  <td
                    colSpan={COLUMNS.length}
                    className="px-6 py-10 text-center text-sm text-slate-400"
                  >
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
                        <FileIcon className="h-4.5 w-4.5 shrink-0 text-red-500" />
                        {d.title}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-block rounded-full px-2.5 py-1 text-[11px] font-medium ${CATEGORY_TONES[d.category] ?? CATEGORY_TONES.General}`}
                      >
                        {d.category}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-400">
                      {d.updated}
                    </td>
                    <td className="px-6 py-4">
                      {d.roles.length > 0 ? (
                        <div className="flex max-w-xs flex-wrap gap-1.5">
                          {d.roles.map((r) => (
                            <RoleTag key={r}>{r}</RoleTag>
                          ))}
                        </div>
                      ) : (
                        <span className="text-sm text-slate-400">
                          No roles assigned
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-4">
                        {/* <button
                          type="button"
                          disabled
                          title="Preview is not available yet"
                          className={`${linkBtn} cursor-not-allowed text-slate-300`}
                        >
                          Preview
                        </button> */}
                        <button
                          type="button"
                          onClick={() => startEdit(d)}
                          // disabled={editing}
                          className={`${linkBtn} text-indigo-600 hover:text-indigo-700 disabled:cursor-not-allowed disabled:text-slate-300 disabled:hover:text-slate-300 cursor-pointer`}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => openDeleteModal(d)}
                          className={`${linkBtn} text-red-400 hover:text-red-700 cursor-pointer`}
                        >
                          Delete
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

      {selectedDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-document-title"
            className="flex h-95 w-full max-w-lg flex-col rounded-2xl bg-white p-6 shadow-xl"
          >
            {/* Modal header */}
            <div className="mb-5 flex items-center justify-between">
              <h2
                id="edit-document-title"
                className="text-lg font-semibold text-slate-900"
              >
                Edit Document Permissions
              </h2>

              <button
                type="button"
                onClick={closeModal}
                aria-label="Close modal"
                className="rounded-lg px-3 py-1 text-xl text-slate-500 hover:bg-slate-100 hover:text-slate-900 cursor-pointer"
              >
                &times;
              </button>
            </div>

            {/* Document name */}
            {/* <p className="mb-2 text-sm text-slate-500">
              Document: {selectedDoc.title}
            </p> */}

            {/* Role selector */}
            <label className="mb-2 block text-sm font-medium text-slate-700">
              Allowed User Roles
            </label>

            <div className="min-h-0 flex-1">
              <RoleSelect
                value={drafts[selectedDoc.id] || []}
                onChange={(roles) => setDraft(selectedDoc.id, roles)}
              />
            </div>

            {/* Modal footer */}
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={closeModal}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 cursor-pointer"
              >
                Close
              </button>

              <button
                type="button"
                onClick={async () => {
                  await submitRoles(selectedDoc.id);
                  setSelectedDoc(null);
                }}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 cursor-pointer"
              >
                Submit
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteDoc && (
        <div
          className="fixed inset-0 z-60 flex items-center justify-center bg-black/50 p-4"
          onClick={(e) => {
            // Close only when the backdrop itself is clicked
            if (e.target === e.currentTarget) {
              closeDeleteModal();
            }
          }}
        >
          <div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-document-title"
            aria-describedby="delete-document-description"
            className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"
          >
            {/* Modal Header */}
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-red-100">
                <svg
                  className="h-6 w-6 text-red-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 9v4m0 4h.01M10.3 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.7 3.86a2 2 0 0 0-3.4 0Z"
                  />
                </svg>
              </div>

              <div className="min-w-0 flex-1">
                <h2
                  id="delete-document-title"
                  className="text-lg font-semibold text-slate-900"
                >
                  Delete Document
                </h2>

                <p
                  id="delete-document-description"
                  className="mt-2 text-sm leading-6 text-slate-500"
                >
                  Are you sure you want to delete{" "}
                  <span className="wrap-break-words font-semibold text-slate-800">
                    "{deleteDoc.title}"
                  </span>
                  ? This action cannot be undone.
                </p>
              </div>

              {/* Close Icon */}
              <button
                type="button"
                onClick={closeDeleteModal}
                disabled={deleting}
                aria-label="Close delete modal"
                className="rounded-lg px-2 py-1 text-xl text-slate-400 transition hover:bg-slate-100 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
              >
                &times;
              </button>
            </div>

            {/* Error Message */}
            {deleteError && (
              <p
                role="alert"
                className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600"
              >
                {deleteError}
              </p>
            )}

            {/* Modal Footer */}
            <div className="mt-7 flex justify-end gap-3">
              <button
                type="button"
                onClick={closeDeleteModal}
                disabled={deleting}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleDelete}
                disabled={deleting}
                className="flex items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {deleting && <RefreshIcon className="h-4 w-4 animate-spin" />}

                {deleting ? "Deleting..." : "Delete Document"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
