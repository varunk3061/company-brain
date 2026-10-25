import { api } from "./http";

export const getUsers = () => api("/users?page=1&page_size=100");

export const createUser = (data) =>
  api("/users", { method: "POST", body: data });

export const updateUser = (userUuid, data) =>
  api(`/users/${userUuid}`, { method: "PUT", body: data });

export const deleteUser = (userUuid) =>
  api(`/users/${userUuid}`, { method: "DELETE" });
