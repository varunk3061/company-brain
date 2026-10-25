"use client";

import { useEffect, useState } from "react";
import { ChevronDownIcon } from "../icons";
import { Eye, EyeOff } from "lucide-react";
import { capitalizeName } from "@/lib/utils";

// Validate email addresses.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const inputBase =
  "block w-full rounded-control border bg-surface-2 px-4 py-3 text-sm text-ink outline-none transition placeholder:text-ink-3 focus:bg-surface focus:ring-4";

const inputOk =
  "border-line focus:border-brand focus:ring-brand/25";

const inputErr = "border-danger/30 focus:border-danger focus:ring-danger/25";

// Reusable dropdown for department and access role.
function SelectField({ id, label, value, onChange, options }) {
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1.5 block text-sm font-medium text-ink-2"
      >
        {label}
      </label>

      <div className="relative">
        <select
          id={id}
          value={value}
          onChange={onChange}
          className={`${inputBase} ${inputOk} appearance-none pr-10`}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        <ChevronDownIcon className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />
      </div>
    </div>
  );
}

// initial: employee being edited, or null when creating.
// takenEmails: emails of other employees.
// onSave: parent function that sends data to the backend.
// onClose: closes the modal.
export default function UserModal({
  initial,
  departments = [],
  roles = [],
  takenEmails = [],
  onSave,
  onClose,
}) {
  const editing = Boolean(initial);

  const [form, setForm] = useState({
    name: initial?.name ?? "",
    email: initial?.email ?? "",
    department_code: initial?.departmentCode ?? departments[0]?.code ?? "",
    role_code: initial?.roleCode ?? "",
  });

  // A role belongs to exactly one department, so the role list follows the department.
  const roleOptions = roles.filter((r) => r.department_code === form.department_code);
  const roleCode = roleOptions.some((r) => r.code === form.role_code)
    ? form.role_code
    : (roleOptions[0]?.code ?? "");

  // Used only when creating a new employee.
  const [password, setPassword] = useState("");

  // For confirm password
  const [confirmPassword, setConfirmPassword] = useState("");

  // For show password and show confirm password
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape" && !saving) {
        onClose();
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose, saving]);

  // Update one field in the form.
  const set = (key) => (event) => {
    setForm((currentForm) => ({
      ...currentForm,
      [key]: event.target.value,
      ...(key === "department_code" ? { role_code: "" } : {}),
    }));

    setErrors((currentErrors) => ({
      ...currentErrors,
      [key]: "",
      submit: "",
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    const name = capitalizeName(form.name);
    const email = form.email.trim().toLowerCase();
    const nextErrors = {};

    // Validate the employee name.
    if (!name) {
      nextErrors.name = "Enter the employee's full name.";
    } else if (name.length < 2 || name.length > 100) {
      nextErrors.name = "Name must contain 2 to 100 characters.";
    }

    if (!form.department_code || !roleCode) {
      nextErrors.role = "Select a department and role.";
    }

    // Validate email.
    if (!email) {
      nextErrors.email = "Enter an email address.";
    } else if (!EMAIL_RE.test(email)) {
      nextErrors.email = "Enter a valid email address.";
    } else {
      const normalizedTakenEmails = takenEmails.map((item) =>
        String(item).trim().toLowerCase(),
      );

      // When editing, allow the employee to keep their own email.
      const currentEmail = String(initial?.email ?? "")
        .trim()
        .toLowerCase();

      if (
        normalizedTakenEmails.includes(email) &&
        (!editing || email !== currentEmail)
      ) {
        nextErrors.email = "An employee with this email already exists.";
      }
    }

    // A password is required only when creating an employee.
    if (!editing) {
      if (!password) {
        nextErrors.password = "Enter a temporary password.";
      } else if (password.length < 12) {
        nextErrors.password = "Password must contain at least 12 characters.";
      } else if (new TextEncoder().encode(password).length > 72) {
        nextErrors.password = "Password must not exceed 72 UTF-8 bytes.";
      }
      if (!confirmPassword) {
        nextErrors.confirmPassword = "Confirm the Password";
      } else if (password !== confirmPassword) {
        nextErrors.confirmPassword = "Passwords do not match.";
      }
    }

    setErrors(nextErrors);

    if (Object.keys(nextErrors).length > 0) {
      return;
    }

    // Build the data sent to the parent component.
    const employeeData = {
      name,
      email,
      department_code: form.department_code,
      role_code: roleCode,
    };

    // Never send a new password as part of an ordinary edit.
    if (!editing) {
      employeeData.password = password;
    }

    try {
      setSaving(true);
      setErrors({});

      // The parent should call the backend API here.
      await onSave(employeeData);
    } catch (error) {
      setErrors({
        submit: error?.message || "Unable to save the employee.",
      });
    } finally {
      setSaving(false);
    }
  };

  //----------------------------------------------------------------------------------------------------------

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-overlay"
        onClick={() => {
          if (!saving) onClose();
        }}
        aria-hidden="true"
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="user-modal-title"
        className="relative max-h-full w-full max-w-md overflow-y-auto rounded-card bg-surface p-6 shadow-pop sm:p-7"
      >
        <h2 id="user-modal-title" className="text-lg font-bold text-ink">
          {editing ? "Edit Employee" : "Add New Employee"}
        </h2>

        <p className="mt-1 text-sm text-ink-3">
          {editing
            ? "Update this user's department and role."
            : "Create an account and assign a department and role."}
        </p>

        <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
          {/* Employee name */}
          <div>
            <label
              htmlFor="emp-name"
              className="mb-1.5 block text-sm font-medium text-ink-2"
            >
              Full name
            </label>

            <input
              id="emp-name"
              type="text"
              autoFocus={!editing}
              disabled={editing}
              value={form.name}
              onChange={set("name")}
              placeholder="Jane Doe"
              autoComplete="name"
              aria-invalid={Boolean(errors.name)}
              className={`${inputBase} ${
                errors.name ? inputErr : inputOk
              } disabled:opacity-60`}
              required
            />

            {errors.name && (
              <p className="mt-1.5 text-xs text-danger">{errors.name}</p>
            )}
          </div>

          {/* Corporate email */}
          <div>
            <label
              htmlFor="emp-email"
              className="mb-1.5 block text-sm font-medium text-ink-2"
            >
              Email{" "}
              {editing && (
                <span className="text-xs text-ink-3 font-normal">
                  (cannot be changed)
                </span>
              )}
            </label>

            <input
              id="emp-email"
              type="email"
              disabled={editing}
              value={form.email}
              onChange={set("email")}
              placeholder="jane.doe@company.com"
              autoComplete="email"
              aria-invalid={Boolean(errors.email)}
              className={`${inputBase} ${
                errors.email ? inputErr : inputOk
              } disabled:opacity-60`}
              required
            />

            {errors.email && (
              <p className="mt-1.5 text-xs text-danger">{errors.email}</p>
            )}
          </div>

          {/* password: only for new employees */}
          {!editing && (
            <>
              <div>
                <label
                  htmlFor="emp-password"
                  className="mb-1.5 block text-sm font-medium text-ink-2"
                >
                  Password
                </label>

                <div className="relative">
                  <input
                    id="emp-password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(event) => {
                      setPassword(event.target.value);

                      setErrors((currentErrors) => ({
                        ...currentErrors,
                        password: "",
                        submit: "",
                      }));
                    }}
                    placeholder="At least 6 characters"
                    autoComplete="new-password"
                    minLength={6}
                    aria-invalid={Boolean(errors.password)}
                    className={`${inputBase} ${
                      errors.password ? inputErr : inputOk
                    }`}
                    required
                  />

                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    aria-label={
                      showPassword ? "Hide Password" : "Show Password"
                    }
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-3 hover:text-ink-2"
                  >
                    {showPassword ? (
                      <EyeOff className="h-5 w-5" />
                    ) : (
                      <Eye className="h-5 w-5" />
                    )}
                  </button>

                  {errors.password && (
                    <p className="mt-1.5 text-xs text-danger">
                      {errors.password}
                    </p>
                  )}
                </div>

                {/* <p className="mt-1.5 text-xs text-ink-3">
                  The backend must hash this password before storing it.
                </p> */}
              </div>

              <div>
                <label
                  htmlFor="emp-confirm-password"
                  className="mb-1.5 block text-sm font-medium text-ink-2"
                >
                  Confirm password
                </label>

                <div className="relative">
                  <input
                    id="emp-confirm-password"
                    type={showConfirmPassword ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(event) => {
                      setConfirmPassword(event.target.value);

                      setErrors((currentErrors) => ({
                        ...currentErrors,
                        confirmPassword: "",
                        submit: "",
                      }));
                    }}
                    placeholder="Re-enter password"
                    autoComplete="new-password"
                    aria-invalid={Boolean(errors.confirmPassword)}
                    className={`${inputBase} ${
                      errors.confirmPassword ? inputErr : inputOk
                    }`}
                    required
                  />

                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword((prev) => !prev)}
                    aria-label={
                      showConfirmPassword
                        ? "Hide Confirm Password"
                        : "Show Confirm Password"
                    }
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-3 hover:text-ink-2"
                  >
                    {showConfirmPassword ? (
                      <EyeOff className="h-5 w-5" />
                    ) : (
                      <Eye className="h-5 w-5" />
                    )}
                  </button>

                  {errors.confirmPassword && (
                    <p className="mt-1.5 text-xs text-danger">
                      {errors.confirmPassword}
                    </p>
                  )}
                </div>
              </div>
            </>
          )}

          {/* Department and access role */}
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField
              id="emp-dept"
              label="Department"
              value={form.department_code}
              onChange={set("department_code")}
              options={departments.map((d) => ({ value: d.code, label: d.name }))}
            />

            <SelectField
              id="emp-role"
              label="Role"
              value={roleCode}
              onChange={set("role_code")}
              options={roleOptions.map((r) => ({ value: r.code, label: r.name }))}
            />
          </div>

          {errors.role && (
            <p className="text-xs text-danger">{errors.role}</p>
          )}

          {/* API or server error */}
          {errors.submit && (
            <p
              role="alert"
              className="rounded-control bg-danger-soft p-3 text-sm text-danger"
            >
              {errors.submit}
            </p>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="rounded-control px-5 py-2.5 text-sm font-medium text-ink-2 transition hover:bg-surface-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:opacity-50"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={saving}
              className="rounded-control bg-brand px-5 py-2.5 text-sm font-semibold text-on-brand shadow-card transition hover:bg-brand-hover focus:outline-none focus-visible:ring-4 focus-visible:ring-brand/25 disabled:opacity-50"
            >
              {saving ? "Saving..." : editing ? "Save Changes" : "Add Employee"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}