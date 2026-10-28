import { api } from "./http";

// Must match MAX_UPLOAD_MB on the backend. The server enforces it; this check only saves a wasted upload.
export const MAX_UPLOAD_MB = 25;

// Upload one PDF: stored in the private bucket, registered, then chunked + embedded.
export const uploadDocument = (file) => {
  const form = new FormData();
  form.append("file", file);
  return api("/api/documents/upload", { method: "POST", body: form });
};

// Short-lived link to the original PDF; the server checks the caller may read the document.
export const getDocumentViewUrl = (documentUuid) =>
  api(`/api/documents/${documentUuid}/view-url`);

// Legacy: register the PDFs in a server-side folder and make them searchable (chunk + embed).
export const scanFolder = (folderPath) =>
  api("/api/documents/scan-and-ingest", {
    method: "POST",
    body: { folder_path: folderPath },
  });

// Documents the signed-in user is allowed to see.
export const getDocuments = () => api("/api/documents/");

// access: { department_code, classification, access: { departments, roles, users } }
export const updateDocumentAccess = (documentUuid, access) =>
  api(`/api/documents/${documentUuid}/access`, {
    method: "PATCH",
    body: access,
  });

export const deleteDocument = (documentUuid) =>
  api(`/api/documents/${documentUuid}`, { method: "DELETE" });
