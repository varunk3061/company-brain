"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Ban, Pencil, RotateCcw, Trash2, X } from "lucide-react";
import { ChevronDownIcon, SearchIcon, UserPlusIcon } from "../icons";
import UserModal from "./UserModal";
import Badge from "@/components/ui/Badge";
import IconButton from "@/components/ui/IconButton";
import Pagination, { PAGE_SIZE } from "@/components/ui/Pagination";
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

// Fixed widths (table-fixed) so columns never resize when filters change the rows.
const COLUMNS = [
  { label: "Name", className: "" },
  { label: "Email", className: "" },
  { label: "Department", className: "w-44" },
  { label: "Role", className: "w-44" },
  { label: "Status", className: "w-28" },
  { label: "Actions", className: "w-40 text-right" },
];

const filterCls =
  "block w-full rounded-control border border-line bg-surface-2 py-2.5 text-sm text-ink outline-none transition placeholder:text-ink-3 focus:border-brand focus:bg-surface focus:ring-4 focus:ring-brand/25";

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
  // Filters
  const [nameQuery, setNameQuery] = useState("");
  const [emailQuery, setEmailQuery] = useState("");
  const [dept, setDept] = useState("");
  const [role, setRole] = useState("");
  const [page, setPage] = useState(1);
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
    const name = nameQuery.trim().toLowerCase();
    const email = emailQuery.trim().toLowerCase();

    return users.filter(
      (user) =>
        (!name || user.name.toLowerCase().includes(name)) &&
        (!email || (user.email ?? "").toLowerCase().includes(email)) &&
        (!dept || user.departmentCode === dept) &&
        (!role || user.roleCode === role),
    );
  }, [users, nameQuery, emailQuery, dept, role]);

  const filtering = Boolean(nameQuery.trim() || emailQuery.trim() || dept || role);

  // Client-side pagination; clamp so deleting the last row of a page falls back a page.
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageUsers = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  // Any filter change starts again from page 1.
  const withPageReset = (setter) => (event) => {
    setter(event.target.value);
    setPage(1);
  };

  const clearFilters = () => {
    setNameQuery("");
    setEmailQuery("");
    setDept("");
    setRole("");
    setPage(1);
  };

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
        {/* Filters */}
        <div className="grid gap-3 px-5 pt-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="relative">
            <SearchIcon className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />
            <input
              type="search"
              value={nameQuery}
              onChange={withPageReset(setNameQuery)}
              placeholder="Search by name..."
              aria-label="Filter by name"
              className={`${filterCls} pl-10 pr-4`}
            />
          </div>

          <div className="relative">
            <SearchIcon className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />
            <input
              type="search"
              value={emailQuery}
              onChange={withPageReset(setEmailQuery)}
              placeholder="Search by email..."
              aria-label="Filter by email"
              className={`${filterCls} pl-10 pr-4`}
            />
          </div>

          <div className="relative">
            <select
              value={dept}
              onChange={withPageReset(setDept)}
              aria-label="Filter by department"
              className={`${filterCls} appearance-none pl-4 pr-10`}
            >
              <option value="">All Departments</option>
              {departments.map((department) => (
                <option key={department.code} value={department.code}>
                  {department.name}
                </option>
              ))}
            </select>
            <ChevronDownIcon className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />
          </div>

          <div className="relative">
            <select
              value={role}
              onChange={withPageReset(setRole)}
              aria-label="Filter by role"
              className={`${filterCls} appearance-none pl-4 pr-10`}
            >
              <option value="">All Roles</option>
              {roles.map((r) => (
                <option key={r.code} value={r.code}>
                  {r.name}
                </option>
              ))}
            </select>
            <ChevronDownIcon className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />
          </div>
        </div>

        {/* Always rendered (hidden when unused) so the filter area never changes size. */}
        <div className="flex items-center justify-between gap-3 px-5 py-3">
          <p className="text-sm text-ink-3">
            {filtering
              ? `Showing ${filtered.length} of ${users.length} users`
              : `Showing all ${users.length} users`}
          </p>
          <button
            type="button"
            onClick={clearFilters}
            disabled={!filtering}
            aria-hidden={!filtering}
            tabIndex={filtering ? 0 : -1}
            className={`inline-flex items-center gap-1.5 rounded-control px-3 py-1.5 text-sm font-medium text-ink-3 transition hover:bg-surface-3 hover:text-ink ${
              filtering ? "" : "invisible"
            }`}
          >
            <X className="h-4 w-4" aria-hidden="true" />
            Clear filters
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-250 table-fixed text-left">
            <thead>
              <tr className="border-y border-line bg-surface-2">
                {COLUMNS.map((column) => (
                  <th
                    key={column.label}
                    scope="col"
                    className={`px-6 py-3.5 text-xs font-semibold uppercase tracking-wider text-ink-3 ${column.className}`}
                  >
                    {column.label}
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
                    {filtering ? "No users match these filters." : "No users yet."}
                  </td>
                </tr>
              )}

              {!loading &&
                pageUsers.map((user) => {
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
                            title={user.name}
                            className={`min-w-0 truncate text-sm font-semibold ${
                              revoked ? "text-ink-3" : "text-ink"
                            }`}
                          >
                            {user.name}
                          </span>
                        </div>
                      </td>

                      <td className="truncate px-6 py-4 text-sm text-ink-3" title={user.email}>
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
                        <div className="flex items-center justify-end gap-1">
                          {/* Edit employee */}
                          <IconButton
                            icon={Pencil}
                            label={`Edit ${user.name}`}
                            tone="brand"
                            onClick={() => setModal({ user })}
                          />

                          {/* Revoke or restore employee access */}
                          <IconButton
                            icon={revoked ? RotateCcw : Ban}
                            label={revoked ? `Restore access for ${user.name}` : `Revoke access for ${user.name}`}
                            tone={revoked ? "success" : "danger"}
                            onClick={() => toggleAccess(user)}
                          />

                          {/* Delete employee */}
                          <IconButton
                            icon={Trash2}
                            label={deletingId === user.id ? "Deleting..." : `Delete ${user.name}`}
                            tone="danger"
                            onClick={() => setDeleteTarget(user)}
                            disabled={deletingId === user.id}
                            busy={deletingId === user.id}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>

        {!loading && (
          <Pagination
            page={currentPage}
            total={filtered.length}
            onPageChange={setPage}
            noun="users"
          />
        )}
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
