import { api } from "./http";

export const getDepartments = () => api("/departments");

export const getRoles = () => api("/roles");

export const createDepartment = (data) =>
  api("/departments", { method: "POST", body: data });

export const updateDepartment = (code, data) =>
  api(`/departments/${code}`, { method: "PUT", body: data });

export const createRole = (data) =>
  api("/roles", { method: "POST", body: data });

export const updateRole = (code, data) =>
  api(`/roles/${code}`, { method: "PUT", body: data });
