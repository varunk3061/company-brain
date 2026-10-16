// Sample data. Replace with real data from your backend.

export const DEPARTMENTS = ["Engineering", "HR", "Security", "Finance", "Operations"];

// Access tiers an employee can be given for RAG retrieval.
export const ACCESS_ROLES = [
  "Admin / Lead",
  "Manager",
  "HR Manager",
  "Security Officer",
  "Employee",
];

// status: Active | Revoked
export const INITIAL_USERS = [
  {
    id: "u1",
    name: "Alex Turner",
    email: "alex.turner@company.com",
    department: "Engineering",
    role: "Admin / Lead",
    status: "Active",
  },
  {
    id: "u2",
    name: "Sarah Jenkins",
    email: "sarah.jenkins@company.com",
    department: "HR",
    role: "HR Manager",
    status: "Active",
  },
  {
    id: "u3",
    name: "Marcus Chen",
    email: "marcus.chen@company.com",
    department: "Security",
    role: "Security Officer",
    status: "Active",
  },
];