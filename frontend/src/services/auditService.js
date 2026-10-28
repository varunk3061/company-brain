import { api } from "./http";

export const getAuditLogs = (page = 1, pageSize = 25) =>
  api(`/audit-logs?page=${page}&page_size=${pageSize}`);
