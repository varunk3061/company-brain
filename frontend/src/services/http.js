import BASE_URL from "@/lib/api";

export function getToken() {
  return (
    localStorage.getItem("access_token") ||
    sessionStorage.getItem("access_token")
  );
}

export function clearSession() {
  localStorage.removeItem("access_token");
  sessionStorage.removeItem("access_token");
}

// FastAPI returns `detail` as a string, or as a list of {msg} for validation errors.
function messageFrom(data, fallback) {
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.detail) && data.detail[0]?.msg)
    return data.detail.map((item) => item.msg).join(" ");
  return fallback;
}

// The one place that knows URLs, the token and error handling.
// A 401 ends the session; anything else throws an Error with a user-safe message.
export async function api(path, { method = "GET", body, auth = true } = {}) {
  const headers = {};

  // FormData (file uploads) is sent as-is: the browser sets the multipart Content-Type and boundary.
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;

  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";

  if (auth) {
    const token = getToken();
    if (!token) {
      throw new Error("NOT_AUTHENTICATED");
    }
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  });

  const data = await response.json().catch(() => ({}));

  if (response.status === 401 && auth) {
    clearSession();
    if (typeof window !== "undefined") window.location.replace("/login");
    throw new Error("NOT_AUTHENTICATED");
  }

  if (!response.ok) {
    throw new Error(messageFrom(data, `Request failed (${response.status}).`));
  }

  return data;
}
