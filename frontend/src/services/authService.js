import { api } from "./http";

// One login for everyone; the backend decides what the user may do.
export function loginUser(credentials) {
  return api("/auth/login", {
    method: "POST",
    auth: false,
    body: { email: credentials.email, password: credentials.password },
  });
}

// Current user: { name, role_name, department_code, permissions[] }.
export function getMyProfile() {
  return api("/auth/me");
}
