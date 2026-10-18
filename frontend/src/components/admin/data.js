// Sample data. Replace with real data from your backend.

export const ADMIN_USER = {
  name: "Alex Turner",
  role: "Engineering Lead",
  initials: "AT",
};

export const NAV_ITEMS = [
  { label: "Dashboard Overview", href: "/admin", icon: "grid" },
  { label: "User / Employee", href: "/admin/users", icon: "users" },
  { label: "Documents & RAG", href: "/admin/documents", icon: "folder" },
  { label: "Audit Logs", href: "/admin/audit-logs", icon: "shield" },
];

export const VECTOR_DB = {
  name: "Vector DB Index",
  detail: "Pinecone v5 \u2022 42,850 vectors",
};

// icon: users | file | chat | shield   tone: indigo | emerald
// note.tone: good | muted   note.icon: trend | check | none
export const STATS = [
  {
    id: "users",
    label: "Total Users",
    value: "1,248",
    icon: "users",
    iconTone: "indigo",
    note: { text: "+12% this month", tone: "good", icon: "trend" },
  },
  {
    id: "docs",
    label: "Indexed Documents",
    value: "342",
    icon: "file",
    iconTone: "emerald",
    note: { text: "100% Validated State", tone: "good", icon: "check" },
  },
  {
    id: "queries",
    label: "Daily RAG Queries",
    value: "8,490",
    icon: "chat",
    iconTone: "indigo",
    note: { text: "Avg latency: 240ms", tone: "muted", icon: "none" },
  },
  {
    id: "security",
    label: "System Security Status",
    value: "Secure",
    icon: "shield",
    iconTone: "emerald",
    note: { text: "RBAC Enforced", tone: "good", icon: "none" },
  },
];

// type: upload | user-add | sync
export const ACTIVITY = [
  {
    id: 1,
    type: "upload",
    event: "Uploaded HR-Policy-Remote-2026.pdf",
    actor: "Sarah Jenkins",
    dept: "HR",
    status: "Indexed",
    time: "10 mins ago",
  },
  {
    id: 2,
    type: "user-add",
    event: "Added new employee account",
    actor: "Alex Turner",
    dept: "Engineering",
    status: "Success",
    time: "1 hour ago",
  },
  {
    id: 3,
    type: "sync",
    event: "Vector Embedding Batch Sync",
    actor: "System Cron",
    dept: "System",
    status: "Completed",
    time: "3 hours ago",
  },
];