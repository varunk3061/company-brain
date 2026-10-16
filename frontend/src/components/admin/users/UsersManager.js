"use client";

import { useMemo, useState } from "react";
import { ChevronDownIcon, SearchIcon, UserPlusIcon } from "../icons";
import UserModal from "./UserModal";
import { DEPARTMENTS, INITIAL_USERS } from "./data";

const uid = () => Math.random().toString(36).slice(2, 10);

const initialsOf = (name) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");

const DEPT_TONES = {
  Engineering: "bg-sky-50 text-sky-600",
  HR: "bg-violet-50 text-violet-600",
  Security: "bg-emerald-50 text-emerald-600",
  Finance: "bg-amber-50 text-amber-700",
  Operations: "bg-slate-100 text-slate-600",
};

const AVATAR_TONES = {
  Engineering: "bg-indigo-100 text-indigo-700",
  HR: "bg-purple-100 text-purple-700",
  Security: "bg-emerald-100 text-emerald-700",
  Finance: "bg-amber-100 text-amber-700",
  Operations: "bg-slate-200 text-slate-700",
};

const STATUS_TONES = {
  Active: "bg-emerald-50 text-emerald-700",
  Revoked: "bg-red-50 text-red-600",
};

const COLUMNS = [
  { label: "Employee Name", className: "" },
  { label: "Email", className: "" },
  { label: "Department", className: "" },
  { label: "Access Role", className: "" },
  { label: "Status", className: "" },
  { label: "Actions", className: "text-right" },
];

const linkBtn =
  "rounded text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500";

export default function UsersManager() {
  const [users, setUsers] = useState(INITIAL_USERS);
  const [query, setQuery] = useState("");
  const [dept, setDept] = useState("All Departments");
  const [modal, setModal] = useState(null); // null | { user: null } (add) | { user } (edit)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return users.filter((u) => {
      const matchesDept = dept === "All Departments" || u.department === dept;
      const matchesQuery =
        !q || u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q);
      return matchesDept && matchesQuery;
    });
  }, [users, query, dept]);

  const editingUser = modal?.user ?? null;
  const takenEmails = users.filter((u) => u.id !== editingUser?.id).map((u) => u.email.toLowerCase());

  const handleSave = (values) => {
    if (editingUser) {
      // TODO: PATCH /api/admin/users/:id
      setUsers((prev) => prev.map((u) => (u.id === editingUser.id ? { ...u, ...values } : u)));
    } else {
      // TODO: POST /api/admin/users
      setUsers((prev) => [{ id: uid(), status: "Active", ...values }, ...prev]);
    }
    setModal(null);
  };

  const toggleAccess = (user) => {
    if (user.status === "Active") {
      if (!window.confirm(`Revoke access for ${user.name}? They will no longer be able to sign in.`)) return;
    }
    // TODO: call your revoke / restore endpoint
    setUsers((prev) =>
      prev.map((u) =>
        u.id === user.id ? { ...u, status: u.status === "Active" ? "Revoked" : "Active" } : u
      )
    );
  };

  return (
    <div className="space-y-8">
      {/* Title row */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            User &amp; Employee Management
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Manage enterprise employee accounts, department permissions, and RAG access tiers.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModal({ user: null })}
          className="flex shrink-0 items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-200 transition hover:bg-indigo-700 focus:outline-none focus-visible:ring-4 focus-visible:ring-indigo-200"
        >
          <UserPlusIcon className="h-4 w-4" />
          Add New Employee
        </button>
      </div>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        {/* Toolbar */}
        <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:max-w-sm">
            <SearchIcon className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search users by name or email..."
              aria-label="Search users"
              className="block w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-100"
            />
          </div>

          <div className="relative">
            <select
              value={dept}
              onChange={(e) => setDept(e.target.value)}
              aria-label="Filter by department"
              className="w-full appearance-none rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-4 pr-10 text-sm text-slate-700 outline-none transition focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-100 sm:w-auto"
            >
              <option>All Departments</option>
              {DEPARTMENTS.map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
            <ChevronDownIcon className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left">
            <thead>
              <tr className="border-y border-slate-200 bg-slate-50">
                {COLUMNS.map((c) => (
                  <th
                    key={c.label}
                    scope="col"
                    className={`px-6 py-3.5 text-xs font-semibold uppercase tracking-wider text-slate-500 ${c.className}`}
                  >
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={COLUMNS.length} className="px-6 py-10 text-center text-sm text-slate-400">
                    No employees match your search.
                  </td>
                </tr>
              )}
              {filtered.map((u) => {
                const revoked = u.status === "Revoked";
                return (
                  <tr key={u.id} className="transition hover:bg-slate-50/60">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${AVATAR_TONES[u.department] ?? AVATAR_TONES.Operations}`}>
                          {initialsOf(u.name)}
                        </span>
                        <span className={`text-sm font-semibold ${revoked ? "text-slate-400" : "text-slate-900"}`}>
                          {u.name}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500">{u.email}</td>
                    <td className="px-6 py-4">
                      <span className={`inline-block rounded-full px-2.5 py-1 text-[11px] font-medium ${DEPT_TONES[u.department] ?? DEPT_TONES.Operations}`}>
                        {u.department}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm font-semibold text-slate-800">{u.role}</td>
                    <td className="px-6 py-4">
                      <span className={`inline-block rounded-full px-2.5 py-1 text-[11px] font-medium ${STATUS_TONES[u.status]}`}>
                        {u.status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-4">
                        <button
                          type="button"
                          onClick={() => setModal({ user: u })}
                          className={`${linkBtn} text-indigo-600 hover:text-indigo-700`}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => toggleAccess(u)}
                          className={`${linkBtn} ${
                            revoked ? "text-emerald-600 hover:text-emerald-700" : "text-red-500 hover:text-red-600"
                          }`}
                        >
                          {revoked ? "Restore" : "Revoke"}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {modal && (
        <UserModal
          initial={editingUser}
          takenEmails={takenEmails}
          onSave={handleSave}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  );
}