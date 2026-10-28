import { api } from "./http";

export const getConversations = () => api("/api/chat/conversations");

export const getConversation = (id) => api(`/api/chat/conversations/${id}`);

export const deleteConversation = (id) =>
  api(`/api/chat/conversations/${id}`, { method: "DELETE" });