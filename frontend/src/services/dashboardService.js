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

// Fetch real stats and recent activity for the admin overview page
export async function getDashboardData() {
  const token = getAdminToken();

  const response = await fetch(`${BASE_URL}/admin/dashboard`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || `Unable to load dashboard (${response.status}).`);
  }

  return data;
}
