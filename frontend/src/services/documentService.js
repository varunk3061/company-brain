import BASE_URL from "../lib/api";

function getAdminToken() {
  const token =
    localStorage.getItem("access_token") ||
    sessionStorage.getItem("access_token");

  if (!token) {
    throw new Error("Admin authentication token not found. Please log in again.");
  }
  return token;
}

// 1. Send folder path to backend to scan & store documents in MongoDB
export async function scanFolder(folderPath) {
  const token = getAdminToken();

  const response = await fetch(`${BASE_URL}/api/documents/scan-folder`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ folder_path: folderPath }),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || `Scan failed (${response.status}).`);
  }

  return data;
}

// 2. Fetch all registered documents from MongoDB
export async function getDocuments() {
  const token = getAdminToken();

  const response = await fetch(`${BASE_URL}/api/documents/`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || `Unable to load documents (${response.status}).`);
  }

  return data;
}

// 3. Update roles permitted to access a document
export async function updateDocumentPermissions(documentUuid, allowedRoles) {
  const token = getAdminToken();

  const response = await fetch(
    `${BASE_URL}/api/documents/${documentUuid}/permissions`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ allowed_roles: allowedRoles }),
    }
  );

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      data.detail || `Unable to update permissions (${response.status}).`
    );
  }

  return data;
}

// 4. Delete a registered document from MongoDB
export async function deleteDocument(documentUuid) {
  const token = getAdminToken();

  const response = await fetch(
    `${BASE_URL}/api/documents/${documentUuid}`,
    {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      data.detail ||
      data.error ||
      `Unable to delete document (${response.status}).`
    );
  }

  return data;
}