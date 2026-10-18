
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ChevronDownIcon,
  SearchIcon,
  UserPlusIcon,
} from "../icons";
import UserModal from "./UserModal";
import { DEPARTMENTS } from "./data";
import { createEmployee, getEmployees, updateEmployee } from "../../../services/employeeService";

const initialsOf = (name = "") =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join("");

const DEPT_TONES = {
  Engineering: "bg-sky-50 text-sky-600",
  IT: "bg-sky-50 text-sky-600",
  HR: "bg-violet-50 text-violet-600",
  Security: "bg-emerald-50 text-emerald-600",
  Finance: "bg-amber-50 text-amber-700",
  Support: "bg-slate-100 text-slate-600",
  Operations: "bg-slate-100 text-slate-600",
};

const AVATAR_TONES = {
  Engineering: "bg-indigo-100 text-indigo-700",
  IT: "bg-indigo-100 text-indigo-700",
  HR: "bg-purple-100 text-purple-700",
  Security: "bg-emerald-100 text-emerald-700",
  Finance: "bg-amber-100 text-amber-700",
  Support: "bg-slate-200 text-slate-700",
  Operations: "bg-slate-200 text-slate-700",
};

const STATUS_TONES = {
  Active: "bg-emerald-50 text-emerald-700",
  Revoked: "bg-red-50 text-red-600",
};

const COLUMNS = [
  "Employee Name",
  "Email",
  "Department",
  "Access Role",
  "Status",
  "Actions",
];

const linkBtn =
  "rounded text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500";

function normalizeEmployee(employee) {
  return {
    id: employee.employee_uuid,
    name: employee.name,
    email: employee.email,
    department: employee.department,
    role: employee.role,
    status: employee.status === "active" ? "Active" : "Revoked",
  };
}

export default function UsersManager() {
  const [users, setUsers] = useState([]);
  const [query, setQuery] = useState("");
  const [dept, setDept] = useState("All Departments");
  const [modal, setModal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pageError, setPageError] = useState("");

  const loadEmployees = useCallback(async () => {
    setPageError("");

    try {
      const result = await getEmployees();
      setUsers(result.items.map(normalizeEmployee));
    } catch (error) {
      setPageError(error.message || "Unable to load employees.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadEmployees();
  }, [loadEmployees]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();

    return users.filter((user) => {
      const matchesDept =
        dept === "All Departments" || user.department === dept;

      const matchesQuery =
        !q ||
        user.name.toLowerCase().includes(q) ||
        user.email.toLowerCase().includes(q);

      return matchesDept && matchesQuery;
    });
  }, [users, query, dept]);

  const editingUser = modal?.user ?? null;

  const takenEmails = users
    .filter((user) => user.id !== editingUser?.id)
    .map((user) => user.email.toLowerCase());

  const handleSave = async (values) => {
    setSaving(true);
    try {
      if (editingUser) {
        await updateEmployee(editingUser.id, {
          department: values.department,
          role: values.role,
          status: editingUser.status === "Active" ? "active" : "blocked",
        });
      } else {
        await createEmployee(values);
      }

      await loadEmployees();
      setModal(null);
    } finally {
      setSaving(false);
    }
  };

  const toggleAccess = async (user) => {
    try {
      const nextStatus = user.status === "Active" ? "blocked" : "active";
      await updateEmployee(user.id, {
        department: user.department,
        role: user.role,
        status: nextStatus,
      });
      await loadEmployees();
    } catch (error) {
      setPageError(error.message || "Unable to update employee status.");
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            User &amp; Employee Management
          </h1>

          <p className="mt-1 text-sm text-slate-500">
            Manage employee accounts, department permissions, and access roles.
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

      {pageError && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
        >
          <span>{pageError}</span>

          <button
            type="button"
            onClick={loadEmployees}
            className="font-semibold underline"
          >
            Retry
          </button>
        </div>
      )}

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:max-w-sm">
            <SearchIcon className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />

            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search users by name or email..."
              aria-label="Search users"
              className="block w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-100"
            />
          </div>

          <div className="relative">
            <select
              value={dept}
              onChange={(event) => setDept(event.target.value)}
              aria-label="Filter by department"
              className="w-full appearance-none rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-4 pr-10 text-sm text-slate-700 outline-none transition focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-100 sm:w-auto"
            >
              <option value="All Departments">All Departments</option>

              {DEPARTMENTS.map((department) => (
                <option key={department} value={department}>
                  {department}
                </option>
              ))}
            </select>

            <ChevronDownIcon className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-225 text-left">
            <thead>
              <tr className="border-y border-slate-200 bg-slate-50">
                {COLUMNS.map((column) => (
                  <th
                    key={column}
                    scope="col"
                    className={`px-6 py-3.5 text-xs font-semibold uppercase tracking-wider text-slate-500 ${
                      column === "Actions" ? "text-right" : ""
                    }`}
                  >
                    {column}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100">
              {loading && (
                <tr>
                  <td
                    colSpan={COLUMNS.length}
                    className="px-6 py-10 text-center text-sm text-slate-500"
                  >
                    Loading employees...
                  </td>
                </tr>
              )}

              {!loading && filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={COLUMNS.length}
                    className="px-6 py-10 text-center text-sm text-slate-400"
                  >
                    No employees match your search.
                  </td>
                </tr>
              )}

              {!loading &&
                filtered.map((user) => {
                  const revoked = user.status === "Revoked";

                  return (
                    <tr
                      key={user.id}
                      className="transition hover:bg-slate-50/60"
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <span
                            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${
                              AVATAR_TONES[user.department] ??
                              AVATAR_TONES.Operations
                            }`}
                          >
                            {initialsOf(user.name)}
                          </span>

                          <span
                            className={`text-sm font-semibold ${
                              revoked
                                ? "text-slate-400"
                                : "text-slate-900"
                            }`}
                          >
                            {user.name}
                          </span>
                        </div>
                      </td>

                      <td className="px-6 py-4 text-sm text-slate-500">
                        {user.email}
                      </td>

                      <td className="px-6 py-4">
                        <span
                          className={`inline-block rounded-full px-2.5 py-1 text-[11px] font-medium ${
                            DEPT_TONES[user.department] ??
                            DEPT_TONES.Operations
                          }`}
                        >
                          {user.department}
                        </span>
                      </td>

                      <td className="px-6 py-4 text-sm font-semibold text-slate-800">
                        {user.role}
                      </td>

                      <td className="px-6 py-4">
                        <span
                          className={`inline-block rounded-full px-2.5 py-1 text-[11px] font-medium ${
                            STATUS_TONES[user.status] ??
                            STATUS_TONES.Revoked
                          }`}
                        >
                          {user.status}
                        </span>
                      </td>

                      <td className="px-6 py-4">
                        <div className="flex items-center justify-end gap-4">
                          <button
                            type="button"
                            onClick={() => setModal({ user })}
                            className={`${linkBtn} text-indigo-600 hover:text-indigo-700`}
                          >
                            Edit
                          </button>

                          <button
                            type="button"
                            onClick={() => toggleAccess(user)}
                            className={`${linkBtn} ${
                              revoked
                                ? "text-emerald-600 hover:text-emerald-700"
                                : "text-red-500 hover:text-red-600"
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