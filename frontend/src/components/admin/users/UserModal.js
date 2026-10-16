"use client";

import { useEffect, useState } from "react";
import { ChevronDownIcon } from "../icons";
import { ACCESS_ROLES, DEPARTMENTS } from "./data";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const inputBase =
  "block w-full rounded-xl border bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:bg-white focus:ring-4";
const inputOk = "border-slate-200 focus:border-indigo-500 focus:ring-indigo-100";
const inputErr = "border-red-300 focus:border-red-500 focus:ring-red-100";

function SelectField({ id, label, value, onChange, options }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <div className="relative">
        <select
          id={id}
          value={value}
          onChange={onChange}
          className={`${inputBase} ${inputOk} appearance-none pr-10`}
        >
          {options.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
        <ChevronDownIcon className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
      </div>
    </div>
  );
}

// `initial` is the user being edited, or null when adding a new employee.
// `takenEmails` are lowercase emails of OTHER users, used to block duplicates.
export default function UserModal({ initial, takenEmails, onSave, onClose }) {
  const editing = !!initial;
  const [form, setForm] = useState({
    name: initial?.name ?? "",
    email: initial?.email ?? "",
    department: initial?.department ?? DEPARTMENTS[0],
    role: initial?.role ?? ACCESS_ROLES[ACCESS_ROLES.length - 1],
  });
  const [errors, setErrors] = useState({});

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSubmit = (e) => {
    e.preventDefault();
    const name = form.name.trim();
    const email = form.email.trim().toLowerCase();
    const next = {};

    if (!name) next.name = "Enter the employee's full name.";
    if (!email) next.email = "Enter an email address.";
    else if (!EMAIL_RE.test(email)) next.email = "Enter a valid email address.";
    else if (takenEmails.includes(email)) next.email = "An employee with this email already exists.";

    setErrors(next);
    if (Object.keys(next).length) return;

    onSave({ name, email, department: form.department, role: form.role });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/40" onClick={onClose} aria-hidden="true" />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="user-modal-title"
        className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-xl sm:p-7"
      >
        <h2 id="user-modal-title" className="text-lg font-bold text-slate-900">
          {editing ? "Edit Employee" : "Add New Employee"}
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          {editing
            ? "Update this employee's details and RAG access tier."
            : "Create an employee account and choose what they can access."}
        </p>

        <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
          <div>
            <label htmlFor="emp-name" className="mb-1.5 block text-sm font-medium text-slate-700">
              Full name
            </label>
            <input
              id="emp-name"
              type="text"
              autoFocus
              value={form.name}
              onChange={set("name")}
              placeholder="Jane Doe"
              aria-invalid={!!errors.name}
              className={`${inputBase} ${errors.name ? inputErr : inputOk}`}
            />
            {errors.name && <p className="mt-1.5 text-xs text-red-600">{errors.name}</p>}
          </div>

          <div>
            <label htmlFor="emp-email" className="mb-1.5 block text-sm font-medium text-slate-700">
              Corporate email
            </label>
            <input
              id="emp-email"
              type="email"
              value={form.email}
              onChange={set("email")}
              placeholder="jane.doe@company.com"
              aria-invalid={!!errors.email}
              className={`${inputBase} ${errors.email ? inputErr : inputOk}`}
            />
            {errors.email && <p className="mt-1.5 text-xs text-red-600">{errors.email}</p>}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField
              id="emp-dept"
              label="Department"
              value={form.department}
              onChange={set("department")}
              options={DEPARTMENTS}
            />
            <SelectField
              id="emp-role"
              label="Access role"
              value={form.role}
              onChange={set("role")}
              options={ACCESS_ROLES}
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl px-5 py-2.5 text-sm font-medium text-slate-600 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-200 transition hover:bg-indigo-700 focus:outline-none focus-visible:ring-4 focus-visible:ring-indigo-200"
            >
              {editing ? "Save Changes" : "Add Employee"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}