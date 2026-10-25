import { api } from "./http";

// Real stats and recent activity for the admin overview page.
export const getDashboardData = () => api("/admin/dashboard");
