import { api } from "./http";

// Register the PDFs in a folder and make them searchable (chunk + embed).
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
