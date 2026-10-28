"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ExternalLink, Eye, Pencil, Search, Trash2, X } from "lucide-react";
import {
  AlertCircleIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  CloudUploadIcon,
  FileIcon,
  FolderIcon,
  RefreshIcon,
} from "../icons";
import {
  MAX_UPLOAD_MB,
  scanFolder,
  getDocuments,
  updateDocumentAccess,
  deleteDocument,
  uploadDocument,
  getDocumentViewUrl,
} from "@/services/documentService";
import { FEATURES } from "@/config/features";
import { getDepartments, getRoles } from "@/services/orgService";
import { getUsers } from "@/services/userService";
import Badge, { ClassificationBadge } from "@/components/ui/Badge";
import DepartmentBadge from "@/components/ui/DepartmentBadge";
import IconButton from "@/components/ui/IconButton";
import { displayName, formatDate } from "@/lib/format";

const CLASSIFICATIONS = [
  { value: "public", label: "Public", hint: "Everyone" },
  { value: "internal", label: "Internal", hint: "Any signed-in employee" },
  {
    value: "confidential",
    label: "Confidential",
    hint: "Owning department (with clearance) + explicit grants",
  },
  { value: "restricted", label: "Restricted", hint: "Explicit grants only" },
];

const COLUMNS = [
  { label: "Document Title", className: "" },
  { label: "Owner Department", className: "" },
  { label: "Classification", className: "" },
  { label: "Explicit Access", className: "" },
  { label: "Last Update", className: "" },
  { label: "Actions", className: "text-right" },
];

const selectCls =
  "block w-full rounded-control border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/25";

const filterCls =
  "block w-full rounded-control border border-line bg-surface-2 py-2.5 text-sm text-ink outline-none transition placeholder:text-ink-3 focus:border-brand focus:bg-surface focus:ring-4 focus:ring-brand/25";

// Explicit grants shown as labelled groups (Departments / Roles / Users), one line each,
// so long lists stay readable instead of one mixed pile of chips.
function AccessGroup({ label, count, children }) {
  if (!count) return null;
  return (
    <div className="flex items-start gap-3">
      <dt className="w-20 shrink-0 pt-1 text-micro font-semibold uppercase tracking-wide text-ink-3">
        {label} <span className="font-normal">({count})</span>
      </dt>
      <dd className="flex min-w-0 flex-1 flex-wrap gap-1.5">{children}</dd>
    </div>
  );
}

// Multi-select with removable chips. Options open inline so the modal's scroll area never clips them.
// options: [{ value, label }]; value: array of option values.
function MultiSelect({ label, options, value, onChange }) {
  const [open, setOpen] = useState(false);

  const labelOf = (v) => options.find((o) => o.value === v)?.label ?? v;

  const toggle = (v) =>
    onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);

  return (
    <div>
      <span className="mb-1.5 block text-sm font-medium text-ink-2">
        {label}
      </span>
      <div className="rounded-control border border-line-strong bg-surface p-2">
        {value.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-1.5">
            {value.map((v) => (
              <span
                key={v}
                className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface py-1 pl-3 pr-2 text-xs text-ink"
              >
                {labelOf(v)}
                <button
                  type="button"
                  onClick={() => toggle(v)}
                  aria-label={`Remove ${labelOf(v)}`}
                  className="rounded-full p-0.5 text-ink-3 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                >
                  &times;
                </button>
              </span>
            ))}
          </div>
        )}

        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="flex w-full items-center justify-between text-left text-xs text-ink-3 transition hover:text-ink-2 focus:outline-none focus-visible:text-brand-text"
        >
          Select {label.toLowerCase()}
          <ChevronDownIcon
            className={`h-4 w-4 transition ${open ? "rotate-180" : ""}`}
          />
        </button>

        {open && (
          <ul className="mt-2 max-h-40 overflow-y-auto">
            {options.length === 0 && (
              <li className="px-2 py-1.5 text-sm text-ink-3">
                Nothing to select.
              </li>
            )}
            {options.map((o) => (
              <li key={o.value}>
                <label className="flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm text-ink-2 hover:bg-surface-2">
                  <input
                    type="checkbox"
                    checked={value.includes(o.value)}
                    onChange={() => toggle(o.value)}
                    className="h-4 w-4 rounded border-line-strong text-brand-text focus:ring-brand"
                  />
                  {o.label}
                </label>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;

// 842113 -> "822 KB"
function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const isPdf = (file) =>
  file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");

// One row per file picked for upload: waiting -> uploading -> done | failed.
const UPLOAD_TONE = {
  waiting: "text-ink-3",
  uploading: "text-ink-2",
  done: "text-success",
  failed: "text-danger",
};

const STATUS_TONE = {
  completed: "success",
  processing: "info",
  uploaded: "info",
  failed: "danger",
};

export default function DocumentsManager() {
  const [docs, setDocs] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [roles, setRoles] = useState([]);
  const [users, setUsers] = useState([]);

  // Document being edited and its unsaved access settings.
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

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

  // PDF preview modal: the document being previewed and its short-lived link.
  const [previewDoc, setPreviewDoc] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const previewRequest = useRef(0);

  // Table filters
  const [titleQuery, setTitleQuery] = useState("");
  const [ownerFilter, setOwnerFilter] = useState("");
  const [classFilter, setClassFilter] = useState("");
  const [accessDeptFilter, setAccessDeptFilter] = useState("");

  // PDF uploads (files go to the backend, which stores them in the private bucket)
  const [uploads, setUploads] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const loadDocuments = useCallback(async () => {
    try {
      const result = await getDocuments();
      setDocs(
        result.map((d) => ({
          id: d.document_uuid,
          title: d.document_name,
          departmentCode: d.department_code,
          classification: d.classification,
          access: d.access,
          needsClassification: d.needs_classification,
          pageCount: d.page_count,
          sizeBytes: d.size_bytes,
          status: d.status,
          lastUpdate: d.last_update,
        })),
      );
    } catch (err) {
      setPathError(err.message || "Failed to load documents.");
    }
  }, []);

  useEffect(() => {
    loadDocuments();
    // Pickers for the access editor; the users list is optional.
    getDepartments().then(setDepartments).catch(() => {});
    getRoles().then(setRoles).catch(() => {});
    getUsers().then((r) => setUsers(r.items)).catch(() => {});
  }, [loadDocuments]);

  const deptName = (code) =>
    departments.find((d) => d.code === code)?.name ?? code;

  const filteredDocs = useMemo(() => {
    const q = titleQuery.trim().toLowerCase();
    return docs.filter(
      (d) =>
        (!q || (d.title ?? "").toLowerCase().includes(q)) &&
        (!ownerFilter ||
          (ownerFilter === "__none__" ? !d.departmentCode : d.departmentCode === ownerFilter)) &&
        (!classFilter || d.classification === classFilter) &&
        (!accessDeptFilter || (d.access?.departments ?? []).includes(accessDeptFilter)),
    );
  }, [docs, titleQuery, ownerFilter, classFilter, accessDeptFilter]);

  const filtering = Boolean(titleQuery.trim() || ownerFilter || classFilter || accessDeptFilter);

  const clearFilters = () => {
    setTitleQuery("");
    setOwnerFilter("");
    setClassFilter("");
    setAccessDeptFilter("");
  };

  // Ask the backend for a short-lived link to the stored PDF (it checks access), then show it in the modal.
  const openPreview = async (doc) => {
    const requestId = ++previewRequest.current;
    setPreviewDoc(doc);
    setPreviewUrl("");
    setPreviewError("");
    setPreviewLoading(true);

    try {
      const result = await getDocumentViewUrl(doc.id);
      if (previewRequest.current === requestId) setPreviewUrl(result.url);
    } catch (err) {
      if (previewRequest.current === requestId)
        setPreviewError(err.message || "Unable to load the document preview.");
    } finally {
      if (previewRequest.current === requestId) setPreviewLoading(false);
    }
  };

  const closePreview = useCallback(() => {
    previewRequest.current += 1; // ignore any response still in flight
    setPreviewDoc(null);
    setPreviewUrl("");
    setPreviewError("");
    setPreviewLoading(false);
  }, []);

  // Escape closes the preview.
  useEffect(() => {
    if (!previewDoc) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") closePreview();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [previewDoc, closePreview]);

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
        `Folder processed: ${result.created_count} new, ${result.existing_count} existing, ${result.ingested_count} ingested, ${result.ingestion_errors?.length || 0} ingestion errors.`,
      );
      setPath("");
    } catch (err) {
      setPathError(err.message || "Failed to scan folder.");
    } finally {
      setSubmitting(false);
    }
  };

  const setUpload = (id, patch) =>
    setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, ...patch } : u)));

  // Check each picked file, then upload the valid ones one at a time (one request per PDF).
  const handleFiles = async (fileList) => {
    const files = Array.from(fileList || []);
    if (files.length === 0 || uploading) return;

    const queue = files.map((file, i) => {
      let message = "";
      if (!isPdf(file)) message = "Only PDF files are supported.";
      else if (file.size > MAX_UPLOAD_BYTES) message = `Larger than ${MAX_UPLOAD_MB} MB.`;
      else if (file.size === 0) message = "The file is empty.";

      return {
        id: `${Date.now()}-${i}`,
        file,
        name: file.name,
        size: file.size,
        state: message ? "failed" : "waiting",
        message,
      };
    });

    setUploads(queue);
    setUploading(true);

    for (const item of queue) {
      if (item.state === "failed") continue;
      setUpload(item.id, { state: "uploading", message: "Uploading and indexing..." });

      try {
        const result = await uploadDocument(item.file);
        const ingestion = result.ingestion || {};
        if (ingestion.status === "failed") {
          setUpload(item.id, {
            state: "failed",
            message: `Stored, but not indexed: ${ingestion.detail || "ingestion failed"}`,
          });
        } else {
          setUpload(item.id, {
            state: "done",
            message: `Indexed: ${result.document?.page_count ?? "?"} pages, ${ingestion.chunk_count ?? 0} chunks.`,
          });
        }
      } catch (err) {
        setUpload(item.id, { state: "failed", message: err.message || "Upload failed." });
      }
    }

    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
    await loadDocuments();
  };

  const startEdit = (doc) => {
    setDraft({
      department_code: doc.departmentCode ?? "",
      classification: doc.classification,
      departments: [...(doc.access?.departments ?? [])],
      roles: [...(doc.access?.roles ?? [])],
      users: [...(doc.access?.users ?? [])],
    });
    setSaveError("");
    setSelectedDoc(doc);
  };

  const closeModal = () => {
    if (saving) return;
    setSelectedDoc(null);
    setDraft(null);
  };

  const submitAccess = async () => {
    setSaving(true);
    setSaveError("");

    try {
      await updateDocumentAccess(selectedDoc.id, {
        department_code: draft.department_code || null,
        classification: draft.classification,
        access: {
          departments: draft.departments,
          roles: draft.roles,
          users: draft.users,
        },
      });
      await loadDocuments();
      setSelectedDoc(null);
      setDraft(null);
    } catch (err) {
      setSaveError(err.message || "Failed to update access.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Title row */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink">
          Corporate Documents &amp; RAG Validation
        </h1>
        <p className="mt-1 text-sm text-ink-3">
          Upload PDF documents to index them, then set the owning department,
          classification and explicit access for each document.
        </p>
      </div>

      {/* PDF upload */}
      <section className="rounded-card border border-line bg-surface p-6 shadow-card">
        <h2 className="text-base font-semibold text-ink">Upload Documents</h2>
        <p className="mt-1 text-sm text-ink-3">
          PDF only, up to {MAX_UPLOAD_MB} MB each. Files are stored privately and indexed for search.
          New documents start as Internal and need classification.
        </p>

        <label
          htmlFor="pdf-upload"
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleFiles(e.dataTransfer.files);
          }}
          className={`mt-4 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-control border-2 border-dashed px-6 py-8 text-center transition focus-within:ring-4 focus-within:ring-brand/25 ${
            dragOver
              ? "border-brand bg-brand-tint/40"
              : "border-line-strong bg-surface-2 hover:border-brand/50"
          } ${uploading ? "pointer-events-none opacity-70" : ""}`}
        >
          {uploading ? (
            <RefreshIcon className="h-7 w-7 animate-spin text-brand-text" />
          ) : (
            <CloudUploadIcon className="h-7 w-7 text-brand-text" />
          )}
          <span className="text-sm font-semibold text-ink">
            {uploading ? "Uploading..." : "Choose PDF files or drag them here"}
          </span>
          <span className="text-xs text-ink-3">You can select several files at once.</span>
          <input
            id="pdf-upload"
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            multiple
            disabled={uploading}
            onChange={(e) => handleFiles(e.target.files)}
            className="sr-only"
          />
        </label>

        {uploads.length > 0 && (
          <ul className="mt-4 divide-y divide-line rounded-control border border-line" aria-live="polite">
            {uploads.map((u) => (
              <li key={u.id} className="flex items-start gap-3 px-4 py-3">
                {u.state === "done" && <CheckCircleIcon className="mt-0.5 h-4 w-4 shrink-0 text-success" />}
                {u.state === "failed" && <AlertCircleIcon className="mt-0.5 h-4 w-4 shrink-0 text-danger" />}
                {u.state === "uploading" && <RefreshIcon className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-ink-3" />}
                {u.state === "waiting" && <FileIcon className="mt-0.5 h-4 w-4 shrink-0 text-ink-3" />}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-ink">
                    {u.name} <span className="font-normal text-ink-3">· {formatBytes(u.size)}</span>
                  </p>
                  <p className={`text-xs ${UPLOAD_TONE[u.state]}`}>
                    {u.message || "Waiting..."}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Folder path (legacy, server-side folder scan) */}
      {FEATURES.legacyFolderScan && (
      <section className="rounded-card border border-line bg-surface p-6 shadow-card">
        <form onSubmit={handlePathSubmit} noValidate>
          <label
            htmlFor="folder-path"
            className="block text-base font-semibold text-ink"
          >
            Document Folder Path
          </label>
          <p className="mt-1 text-sm text-ink-3">
            Enter the path to the folder that contains the documents to index.
          </p>

          <div className="mt-4 flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <FolderIcon className="pointer-events-none absolute left-4 top-1/2 h-4.5 w-4.5 -translate-y-1/2 text-ink-3" />
              <input
                id="folder-path"
                type="text"
                value={path}
                onChange={(e) => setPath(e.target.value)}
                placeholder="/mnt/company-docs/hr-policies"
                aria-invalid={!!pathError}
                className={`block w-full rounded-control border bg-surface-2 py-3 pl-11 pr-4 text-sm text-ink outline-none transition placeholder:text-ink-3 focus:bg-surface focus:ring-4 ${
                  pathError
                    ? "border-danger/30 focus:border-danger focus:ring-danger/25"
                    : "border-line focus:border-brand focus:ring-brand/25"
                }`}
              />
            </div>
            <button
              type="submit"
              disabled={submitting}
              className="flex items-center justify-center gap-2 rounded-control bg-brand px-6 py-3 text-sm font-semibold text-on-brand shadow-card transition hover:bg-brand-hover focus:outline-none focus-visible:ring-4 focus-visible:ring-brand/25 disabled:opacity-70"
            >
              {submitting && <RefreshIcon className="h-4 w-4 animate-spin" />}
              {submitting ? "Submitting..." : "Submit"}
            </button>
          </div>

          {pathError && (
            <p role="alert" className="mt-2 text-sm text-danger">
              {pathError}
            </p>
          )}
          {submittedPath && (
            <p
              role="status"
              className="mt-3 flex items-center gap-1.5 text-sm text-success"
            >
              <CheckCircleIcon className="h-4 w-4 shrink-0" />
              <span className="break-all">
                Folder submitted for indexing: {submittedPath}
              </span>
            </p>
          )}
        </form>
      </section>
      )}

      {/* Table */}
      <section className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
        <div className="flex items-center justify-between gap-4 px-6 py-5">
          <h2 className="text-base font-semibold text-ink">
            Ingested Document Knowledge States
          </h2>
          <p className="shrink-0 text-sm text-ink-3">
            {filtering
              ? `Showing ${filteredDocs.length} of ${docs.length} documents`
              : `Showing all ${docs.length} documents`}
          </p>
        </div>

        {/* Filters */}
        <div className="grid gap-3 px-6 pb-5 sm:grid-cols-2 lg:grid-cols-4">
          <div className="relative">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
            <input
              type="search"
              value={titleQuery}
              onChange={(e) => setTitleQuery(e.target.value)}
              placeholder="Search by document title..."
              aria-label="Filter by document title"
              className={`${filterCls} pl-10 pr-4`}
            />
          </div>
          <select
            value={ownerFilter}
            onChange={(e) => setOwnerFilter(e.target.value)}
            aria-label="Filter by owner department"
            className={`${filterCls} px-4`}
          >
            <option value="">All owner departments</option>
            <option value="__none__">No owner department</option>
            {departments.map((d) => (
              <option key={d.code} value={d.code}>{d.name}</option>
            ))}
          </select>
          <select
            value={classFilter}
            onChange={(e) => setClassFilter(e.target.value)}
            aria-label="Filter by classification"
            className={`${filterCls} px-4`}
          >
            <option value="">All classifications</option>
            {CLASSIFICATIONS.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
          <select
            value={accessDeptFilter}
            onChange={(e) => setAccessDeptFilter(e.target.value)}
            aria-label="Filter by department with access"
            className={`${filterCls} px-4`}
          >
            <option value="">All access departments</option>
            {departments.map((d) => (
              <option key={d.code} value={d.code}>{d.name}</option>
            ))}
          </select>
          {filtering && (
            <button
              type="button"
              onClick={clearFilters}
              className="inline-flex items-center gap-1.5 justify-self-start rounded-control px-3 py-2 text-sm font-medium text-ink-3 transition hover:bg-surface-3 hover:text-ink"
            >
              <X className="h-4 w-4" aria-hidden="true" />
              Clear filters
            </button>
          )}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-250 text-left">
            <thead>
              <tr className="border-y border-line bg-surface-2">
                {COLUMNS.map((c) => (
                  <th
                    key={c.label}
                    scope="col"
                    className={`px-6 py-3.5 text-xs font-semibold uppercase tracking-wider text-ink-3 ${c.className}`}
                  >
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {docs.length === 0 && (
                <tr>
                  <td
                    colSpan={COLUMNS.length}
                    className="px-6 py-10 text-center text-sm text-ink-3"
                  >
                    No documents yet. Upload a PDF to get started.
                  </td>
                </tr>
              )}
              {docs.length > 0 && filteredDocs.length === 0 && (
                <tr>
                  <td
                    colSpan={COLUMNS.length}
                    className="px-6 py-10 text-center text-sm text-ink-3"
                  >
                    No documents match these filters.
                  </td>
                </tr>
              )}
              {filteredDocs.map((d) => (
                <tr key={d.id} className="transition hover:bg-surface-2/60">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3 text-sm font-medium text-ink">
                      <FileIcon className="h-4.5 w-4.5 shrink-0 text-danger" />
                      <span className="min-w-0 wrap-break-word">{d.title}</span>
                      <IconButton
                        icon={Eye}
                        label={`Preview ${d.title}`}
                        tone="brand"
                        onClick={() => openPreview(d)}
                      />
                    </div>
                    {(d.pageCount || d.sizeBytes || d.status) && (
                      <div className="mt-1 flex flex-wrap items-center gap-2 pl-7.5 text-xs text-ink-3">
                        {d.pageCount ? <span>{d.pageCount} pages</span> : null}
                        {d.sizeBytes ? <span>{formatBytes(d.sizeBytes)}</span> : null}
                        {d.status && (
                          <Badge tone={STATUS_TONE[d.status] ?? "neutral"}>
                            {d.status.charAt(0).toUpperCase() + d.status.slice(1)}
                          </Badge>
                        )}
                      </div>
                    )}
                    {d.needsClassification && (
                      <span className="mt-1 inline-block rounded-full bg-warning-soft px-2 py-0.5 text-micro font-semibold uppercase tracking-wide text-warning">
                        Needs Classification
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-ink-2">
                    {d.departmentCode ? deptName(d.departmentCode) : "—"}
                  </td>
                  <td className="px-6 py-4">
                    <ClassificationBadge value={d.classification} />
                  </td>
                  <td className="min-w-80 px-6 py-4">
                    {(d.access?.departments?.length ?? 0) +
                      (d.access?.roles?.length ?? 0) +
                      (d.access?.users?.length ?? 0) >
                    0 ? (
                      <dl className="max-w-sm space-y-2">
                        <AccessGroup label="Depts" count={d.access.departments?.length}>
                          {d.access.departments.map((c) => (
                            <DepartmentBadge key={`d-${c}`} code={c}>{deptName(c)}</DepartmentBadge>
                          ))}
                        </AccessGroup>
                        <AccessGroup label="Roles" count={d.access.roles?.length}>
                          {d.access.roles.map((c) => (
                            <Badge key={`r-${c}`} tone="neutral">
                              {roles.find((r) => r.code === c)?.name ?? c}
                            </Badge>
                          ))}
                        </AccessGroup>
                        <AccessGroup label="Users" count={d.access.users?.length}>
                          {d.access.users.map((u) => (
                            <Badge key={`u-${u}`} tone="brand">
                              {displayName(users.find((x) => x.user_uuid === u)?.name) || "User"}
                            </Badge>
                          ))}
                        </AccessGroup>
                      </dl>
                    ) : (
                      <span className="text-sm text-ink-3">No explicit grants</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-ink-3">{formatDate(d.lastUpdate)}</td>
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end gap-1">
                      <IconButton
                        icon={Pencil}
                        label={`Edit access for ${d.title}`}
                        tone="brand"
                        onClick={() => startEdit(d)}
                      />
                      <IconButton
                        icon={Trash2}
                        label={`Delete ${d.title}`}
                        tone="danger"
                        onClick={() => openDeleteModal(d)}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {selectedDoc && draft && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-document-title"
            className="flex max-h-full w-full max-w-xl flex-col rounded-card bg-surface p-6 shadow-pop"
          >
            <div className="mb-4 flex items-center justify-between">
              <div className="min-w-0">
                <h2
                  id="edit-document-title"
                  className="text-lg font-semibold text-ink"
                >
                  Edit Document Access
                </h2>
                <p className="truncate text-sm text-ink-3">{selectedDoc.title}</p>
              </div>
              <button
                type="button"
                onClick={closeModal}
                aria-label="Close modal"
                className="rounded-control px-3 py-1 text-xl text-ink-3 hover:bg-surface-3 hover:text-ink"
              >
                &times;
              </button>
            </div>

            <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="doc-dept" className="mb-1.5 block text-sm font-medium text-ink-2">
                    Owning department
                  </label>
                  <select
                    id="doc-dept"
                    value={draft.department_code}
                    onChange={(e) => setDraft({ ...draft, department_code: e.target.value })}
                    className={selectCls}
                  >
                    <option value="">None</option>
                    {departments.map((d) => (
                      <option key={d.code} value={d.code}>{d.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="doc-class" className="mb-1.5 block text-sm font-medium text-ink-2">
                    Classification
                  </label>
                  <select
                    id="doc-class"
                    value={draft.classification}
                    onChange={(e) => setDraft({ ...draft, classification: e.target.value })}
                    className={selectCls}
                  >
                    {CLASSIFICATIONS.map((c) => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              <p className="text-xs text-ink-3">
                {CLASSIFICATIONS.find((c) => c.value === draft.classification)?.hint}.
                Explicit grants below always apply, on top of the classification rule.
              </p>

              <MultiSelect
                label="Departments"
                options={departments.map((d) => ({ value: d.code, label: d.name }))}
                value={draft.departments}
                onChange={(v) => setDraft({ ...draft, departments: v })}
              />
              <MultiSelect
                label="Roles"
                options={roles.map((r) => ({ value: r.code, label: r.name }))}
                value={draft.roles}
                onChange={(v) => setDraft({ ...draft, roles: v })}
              />
              <MultiSelect
                label="Specific users"
                options={users.map((u) => ({ value: u.user_uuid, label: `${displayName(u.name)} (${u.role_name})` }))}
                value={draft.users}
                onChange={(v) => setDraft({ ...draft, users: v })}
              />
            </div>

            {saveError && (
              <p role="alert" className="mt-4 rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">
                {saveError}
              </p>
            )}

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={closeModal}
                disabled={saving}
                className="rounded-control border border-line-strong px-4 py-2 text-sm font-medium text-ink-2 hover:bg-surface-2 disabled:opacity-50"
              >
                Close
              </button>
              <button
                type="button"
                onClick={submitAccess}
                disabled={saving}
                className="rounded-control bg-brand px-4 py-2 text-sm font-semibold text-on-brand hover:bg-brand-hover disabled:opacity-60"
              >
                {saving ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* PDF Preview Modal */}
      {previewDoc && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4"
          onClick={(e) => {
            // Close only when the backdrop itself is clicked
            if (e.target === e.currentTarget) closePreview();
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="preview-document-title"
            className="flex h-full w-full max-w-5xl flex-col rounded-card bg-surface shadow-pop"
          >
            <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
              <div className="flex min-w-0 items-center gap-2.5">
                <FileIcon className="h-4.5 w-4.5 shrink-0 text-danger" />
                <h2 id="preview-document-title" className="truncate text-base font-semibold text-ink">
                  {previewDoc.title}
                </h2>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                {previewUrl && (
                  <a
                    href={previewUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Open in a new tab"
                    title="Open in a new tab"
                    className="inline-flex h-8 w-8 items-center justify-center rounded-control text-ink-3 transition hover:bg-surface-3 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                  >
                    <ExternalLink className="h-4 w-4" aria-hidden="true" />
                  </a>
                )}
                <IconButton icon={X} label="Close preview" onClick={closePreview} />
              </div>
            </div>

            <div className="min-h-0 flex-1 p-3">
              {previewLoading && (
                <div className="flex h-full items-center justify-center gap-2 text-sm text-ink-3">
                  <RefreshIcon className="h-4 w-4 animate-spin" />
                  Loading preview...
                </div>
              )}
              {!previewLoading && previewError && (
                <div className="flex h-full items-center justify-center">
                  <p role="alert" className="flex items-center gap-2 rounded-control bg-danger-soft px-4 py-3 text-sm text-danger">
                    <AlertCircleIcon className="h-4 w-4 shrink-0" />
                    {previewError}
                  </p>
                </div>
              )}
              {!previewLoading && !previewError && previewUrl && (
                <iframe
                  src={previewUrl}
                  title={`Preview of ${previewDoc.title}`}
                  className="h-full w-full rounded-control border border-line bg-surface-2"
                />
              )}
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteDoc && (
        <div
          className="fixed inset-0 z-60 flex items-center justify-center bg-overlay p-4"
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
            className="w-full max-w-md rounded-card bg-surface p-6 shadow-pop"
          >
            {/* Modal Header */}
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-danger-soft">
                <svg
                  className="h-6 w-6 text-danger"
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
                  className="text-lg font-semibold text-ink"
                >
                  Delete Document
                </h2>

                <p
                  id="delete-document-description"
                  className="mt-2 text-sm leading-6 text-ink-3"
                >
                  Are you sure you want to delete{" "}
                  <span className="wrap-break-words font-semibold text-ink">
                    &quot;{deleteDoc.title}&quot;
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
                className="rounded-control px-2 py-1 text-xl text-ink-3 transition hover:bg-surface-3 hover:text-ink disabled:opacity-50"
              >
                &times;
              </button>
            </div>

            {/* Error Message */}
            {deleteError && (
              <p
                role="alert"
                className="mt-4 rounded-control bg-danger-soft px-3 py-2 text-sm text-danger"
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
                className="rounded-control border border-line-strong px-4 py-2 text-sm font-medium text-ink-2 transition hover:bg-surface-2 disabled:opacity-50"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleDelete}
                disabled={deleting}
                className="flex items-center justify-center gap-2 rounded-control bg-danger px-4 py-2 text-sm font-semibold text-on-danger transition hover:bg-danger-hover disabled:opacity-60"
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
