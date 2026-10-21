
import BASE_URL from "../lib/api";

// Get the currently logged-in employee's profile.
export async function getMyProfile() {
  const token =
    localStorage.getItem("access_token") ||
    sessionStorage.getItem("access_token");

  if (!token) {
    throw new Error(
      "Authentication token not found. Please log in again."
    );
  }

  const response = await fetch(`${BASE_URL}/employee/me`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      data.detail ||
        `Unable to fetch employee profile (${response.status}).`
    );
  }

  return data;
}

//-----------------------------------------------------------------------------------------

// Create a new employee from the admin employee-management page.
export async function createEmployee(employeeData) {
  const token =
    localStorage.getItem("access_token") ||
    sessionStorage.getItem("access_token");

  if (!token) {
    throw new Error(
      "Authentication token not found. Please log in again."
    );
  }

  const response = await fetch(`${BASE_URL}/employees`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(employeeData),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Unable to create employee (${response.status}).`
    );
  }

  return data;
}

//-----------------------------------------------------------------------------------------

// GET all employee
export async function getEmployees() {
  const token =
    localStorage.getItem("access_token") ||
    sessionStorage.getItem("access_token");

  if (!token) {
    throw new Error("Admin authentication token not found. Please log in again.");
  }

  const response = await fetch(`${BASE_URL}/employees?page=1&page_size=100`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      data.detail || `Unable to load employees (${response.status}).`
    );
  }

  return data;
}

//-----------------------------------------------------------------------------------------

// Updating existing employee using PUT
export async function updateEmployee(employeeUuid, updateData) {
  const token =
    localStorage.getItem("access_token") ||
    sessionStorage.getItem("access_token");

  if (!token) {
    throw new Error("Admin authentication token not found. Please log in again.");
  }

  const response = await fetch(`${BASE_URL}/employees/${employeeUuid}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(updateData),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Unable to update employee (${response.status}).`
    );
  }

  return data;
}

//-----------------------------------------------------------------------------------------

export async function deleteEmployee(employeeUuid) {
  const url = `${BASE_URL}/employees/${employeeUuid}`;

  console.log("Delete URL:", url);
  console.log("Employee UUID:", employeeUuid);

  const token = localStorage.getItem("access_token");

  const response = await fetch(url, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  console.log("Delete status:", response.status);

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || "Unable to delete employee.");
  }

  return data;
}