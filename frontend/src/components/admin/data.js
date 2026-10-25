// Which permission unlocks each admin page. The server still enforces every rule.
export const NAV_ITEMS = [
  { label: "Dashboard Overview", href: "/admin", icon: "grid", permission: "users.manage" },
  { label: "Users", href: "/admin/users", icon: "users", permission: "users.manage" },
  { label: "Organisation", href: "/admin/organisation", icon: "org", permission: "org.manage" },
  { label: "Documents & RAG", href: "/admin/documents", icon: "folder", permission: "documents.manage" },
  { label: "Audit Logs", href: "/admin/audit-logs", icon: "shield", permission: "audit.read" },
];

// Holding any of these means the user belongs in the control center.
export const ADMIN_PERMISSIONS = [
  "users.manage",
  "org.manage",
  "documents.manage",
  "audit.read",
];
