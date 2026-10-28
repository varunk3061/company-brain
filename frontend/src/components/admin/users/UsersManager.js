"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDownIcon, SearchIcon, UserPlusIcon } from "../icons";
import UserModal from "./UserModal";
import Badge from "@/components/ui/Badge";
import DepartmentBadge from "@/components/ui/DepartmentBadge";
import { displayName } from "@/lib/format";
import { createUser, getUsers, updateUser, deleteUser } from "@/services/userService";
import { getDepartments, getRoles } from "@/services/orgService";

const initialsOf = (name = "") =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join("");

const COLUMNS = [
  "Name",
  "Email",
  "Department",
  "Role",
  "Status",
  "Actions",
];

const linkBtn =
  "rounded text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand";

function normalizeUser(user) {
  return {
    id: user.user_uuid,
    name: displayName(user.name),
    email: user.email,
    departmentCode: user.department_code,
    departmentName: user.department_name,
    roleCode: user.role_code,
    roleName: user.role_name,
    status: user.status === "active" ? "Active" : "Revoked",
  };
}

export default function UsersManager() {
  const [users, setUsers] = useState([]);
  const [query, setQuery] = useState("");
  const [dept, setDept] = useState("All Departments");
  const [departments, setDepartments] = useState([]);
  const [roles, setRoles] = useState([]);
  const [modal, setModal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pageError, setPageError] = useState("");
  const [deletingId, setDeletingId] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);

  const loadEmployees = useCallback(async () => {
    setPageError("");

    try {
      const [result, departmentList, roleList] = await Promise.all([
        getUsers(),
        getDepartments(),
        getRoles(),
      ]);
      setUsers(result.items.map(normalizeUser));
      setDepartments(departmentList.filter((d) => d.status === "active"));
      setRoles(roleList.filter((r) => r.status === "active"));
    } catch (error) {
      setPageError(error.message || "Unable to load users.");
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
        dept === "All Departments" || user.departmentCode === dept;

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
        await updateUser(editingUser.id, {
          name: values.name,
          department_code: values.department_code,
          role_code: values.role_code,
        });
      } else {
        await createUser(values);
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
      await updateUser(user.id, { status: nextStatus });
      await loadEmployees();
    } catch (error) {
      setPageError(error.message || "Unable to update user status.");
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;

    const user = deleteTarget;

    setDeletingId(user.id);
    setPageError("");

    try {
      await deleteUser(user.id);

      setUsers((previousUsers) =>
        previousUsers.filter((item) => item.id !== user.id),
      );

      setDeleteTarget(null);
    } catch (error) {
      setPageError(error.message || "Unable to delete user.");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">
            User Management
          </h1>

          <p className="mt-1 text-sm text-ink-3">
            Manage user accounts and assign each person a department and role.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setModal({ user: null })}
          className="flex shrink-0 items-center gap-2 rounded-control bg-brand px-5 py-3 text-sm font-semibold text-on-brand shadow-card transition hover:bg-brand-hover focus:outline-none focus-visible:ring-4 focus-visible:ring-brand/25"
        >
          <UserPlusIcon className="h-4 w-4" />
          Add New User
        </button>
      </div>

      {pageError && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-danger/30 bg-danger-soft p-4 text-sm text-danger"
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

      <section className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
        <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:max-w-sm">
            <SearchIcon className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />

            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search users by name or email..."
              aria-label="Search users"
              className="block w-full rounded-control border border-line bg-surface-2 py-2.5 pl-10 pr-4 text-sm text-ink outline-none transition placeholder:text-ink-3 focus:border-brand focus:bg-surface focus:ring-4 focus:ring-brand/25"
            />
          </div>

          <div className="relative">
            <select
              value={dept}
              onChange={(event) => setDept(event.target.value)}
              aria-label="Filter by department"
              className="w-full appearance-none rounded-control border border-line bg-surface-2 py-2.5 pl-4 pr-10 text-sm text-ink-2 outline-none transition focus:border-brand focus:bg-surface focus:ring-4 focus:ring-brand/25 sm:w-auto"
            >
              <option value="All Departments">All Departments</option>

              {departments.map((department) => (
                <option key={department.code} value={department.code}>
                  {department.name}
                </option>
              ))}
            </select>

            <ChevronDownIcon className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3 " />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-225 text-left">
            <thead>
              <tr className="border-y border-line bg-surface-2">
                {COLUMNS.map((column) => (
                  <th
                    key={column}
                    scope="col"
                    className={`px-6 py-3.5 text-xs font-semibold uppercase tracking-wider text-ink-3 ${
                      column === "Actions" ? "text-right" : ""
                    }`}
                  >
                    {column}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody className="divide-y divide-line">
              {loading && (
                <tr>
                  <td
                    colSpan={COLUMNS.length}
                    className="px-6 py-10 text-center text-sm text-ink-3"
                  >
                    Loading users...
                  </td>
                </tr>
              )}

              {!loading && filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={COLUMNS.length}
                    className="px-6 py-10 text-center text-sm text-ink-3"
                  >
                    No users match your search.
                  </td>
                </tr>
              )}

              {!loading &&
                filtered.map((user) => {
                  const revoked = user.status === "Revoked";

                  return (
                    <tr
                      key={user.id}
                      className="transition hover:bg-surface-2/60"
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <span
                            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-tint text-micro font-bold text-brand-text"
                          >
                            {initialsOf(user.name)}
                          </span>

                          <span
                            className={`text-sm font-semibold ${
                              revoked ? "text-ink-3" : "text-ink"
                            }`}
                          >
                            {user.name}
                          </span>
                        </div>
                      </td>

                      <td className="px-6 py-4 text-sm text-ink-3">
                        {user.email}
                      </td>

                      <td className="px-6 py-4">
                        <DepartmentBadge code={user.departmentCode}>{user.departmentName}</DepartmentBadge>
                      </td>

                      <td className="px-6 py-4 text-sm font-semibold text-ink">
                        {user.roleName}
                      </td>

                      <td className="px-6 py-4">
                        <Badge tone={revoked ? "danger" : "success"}>{user.status}</Badge>
                      </td>

                      <td className="px-6 py-4">
                        <div className="flex items-center justify-end gap-4">
                          {/* Edit employee */}
                          <button
                            type="button"
                            onClick={() => setModal({ user })}
                            className={`${linkBtn} text-brand-text hover:text-brand-text`}
                          >
                            Edit
                          </button>

                          {/* Revoke or restore employee access */}
                          <button
                            type="button"
                            onClick={() => toggleAccess(user)}
                            className={`${linkBtn} ${
                              revoked
                                ? "text-success hover:text-success"
                                : "text-danger hover:text-danger"
                            }`}
                          >
                            {revoked ? "Restore" : "Revoke"}
                          </button>

                          {/* Delete employee */}
                          <button
                            type="button"
                            onClick={() => setDeleteTarget(user)}
                            disabled={deletingId === user.id}
                            className={`${linkBtn} text-danger hover:text-danger disabled:opacity-50`}
                          >
                            {deletingId === user.id ? "Deleting..." : "Delete"}
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
          departments={departments}
          roles={roles}
          takenEmails={takenEmails}
          onSave={handleSave}
          onClose={() => setModal(null)}
        />
      )}

      {deleteTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4 backdrop-blur-sm"
          onClick={() => {
            if (deletingId === null) setDeleteTarget(null);
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-modal-title"
            className="w-full max-w-md rounded-card border border-line bg-surface p-6 shadow-pop cursor-default"
            onClick={(event) => event.stopPropagation()}
          >
            {/* Warning icon and heading */}
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-danger-soft">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  className="h-6 w-6 text-danger"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 9v4m0 4h.01M10.3 3.9 2.7 17.1A2 2 0 0 0 4.4 20h15.2a2 2 0 0 0 1.7-2.9L13.7 3.9a2 2 0 0 0-3.4 0Z"
                  />
                </svg>
              </div>

              <div className="min-w-0 flex-1">
                <h2
                  id="delete-modal-title"
                  className="text-lg font-bold text-ink"
                >
                  Delete User
                </h2>

                <p className="mt-2 text-sm leading-6 text-ink-2">
                  Are you sure you want to permanently delete{" "}
                  <span className="font-semibold text-ink">
                    {deleteTarget.name}
                  </span>
                  ?
                </p>

                <p className="mt-2 text-sm text-danger">
                  This action cannot be undone.
                </p>
              </div>
            </div>

            {/* Employee details */}
            <div className="mt-5 rounded-control border border-line bg-surface-2 p-4">
              <p className="truncate text-sm font-semibold text-ink">
                {deleteTarget.name}
              </p>
              <p className="mt-1 truncate text-sm text-ink-3">
                {deleteTarget.email}
              </p>
              <p className="mt-2 text-xs text-ink-3">
                {deleteTarget.departmentName} · {deleteTarget.roleName}
              </p>
            </div>

            {/* Modal actions */}
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                disabled={deletingId !== null}
                onClick={() => setDeleteTarget(null)}
                className="rounded-control border border-line px-4 py-2.5 text-sm font-semibold text-ink-2 transition hover:bg-surface-2 disabled:opacity-50"
              >
                Cancel
              </button>

              <button
                type="button"
                disabled={deletingId !== null}
                onClick={handleDelete}
                className="rounded-control bg-danger px-4 py-2.5 text-sm font-semibold text-on-danger shadow-card transition hover:bg-danger-hover disabled:opacity-60"
              >
                {deletingId === deleteTarget.id
                  ? "Deleting..."
                  : "Delete User"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
