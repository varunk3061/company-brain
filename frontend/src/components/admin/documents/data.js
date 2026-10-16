// Sample data. Replace with real data from your backend.

// Total documents in the knowledge base (the table below shows a page of them).
export const TOTAL_DOCUMENTS = 342;

// User roles that can be allowed to access a document.
export const USER_ROLES = [
  "Admin",
  "Manager",
  "HR",
  "Engineering",
  "Finance",
  "Security",
  "Employee",
];

export const INITIAL_DOCUMENTS = [
  {
    id: "d1",
    title: "HR-Policy-Remote-2026.pdf",
    category: "HR",
    updated: "Today, 10:42 AM",
    roles: ["HR", "Manager"],
  },
  {
    id: "d2",
    title: "Microservice-Architecture-v3.md",
    category: "Engineering",
    updated: "Yesterday",
    roles: ["Engineering"],
  },
  {
    id: "d3",
    title: "Q4-Security-Compliance-Audit.pdf",
    category: "Security",
    updated: "Oct 12, 2026",
    roles: ["Security", "Admin"],
  },
];