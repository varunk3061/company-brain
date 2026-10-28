import { api } from "./http";

// filters: { action, actor } — both optional. `action` is an exact action ("user.create"),
// `actor` matches part of the actor's name or email.
export const getAuditLogs = (page = 1, pageSize = 25, filters = {}) => {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (filters.action) params.set("action", filters.action);
  if (filters.actor?.trim()) params.set("actor", filters.actor.trim());
  return api(`/audit-logs?${params.toString()}`);
};
