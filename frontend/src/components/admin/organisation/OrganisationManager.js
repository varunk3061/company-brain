"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createDepartment,
  createRole,
  getDepartments,
  getRoles,
  updateDepartment,
  updateRole,
} from "@/services/orgService";

const CLEARANCES = ["public", "internal", "confidential", "restricted"];

const PERMISSION_LABELS = {
  "users.manage": "Manage users",
  "org.manage": "Manage organisation",
  "documents.manage": "Manage documents",
  "documents.approve": "Approve documents",
  "audit.read": "Read audit log",
};

const inputCls =
  "block w-full rounded-control border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/25";

const linkBtn =
  "rounded text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand";

export default function OrganisationManager() {
  const [departments, setDepartments] = useState([]);
  const [roles, setRoles] = useState([]);
  const [error, setError] = useState("");
  const [deptForm, setDeptForm] = useState({ code: "", name: "" });
  const [roleForm, setRoleForm] = useState({ department_code: "", code: "", name: "", clearance: "internal" });

  const load = useCallback(async () => {
    try {
      const [d, r] = await Promise.all([getDepartments(), getRoles()]);
      setDepartments(d);
      setRoles(r);
      setError("");
    } catch (err) {
      setError(err.message || "Unable to load the organisation.");
    }
  }, []);

  // Initial load: state is set in the promise callback, not synchronously in the effect.
  useEffect(() => {
    let alive = true;
    Promise.all([getDepartments(), getRoles()])
      .then(([d, r]) => {
        if (!alive) return;
        setDepartments(d);
        setRoles(r);
      })
      .catch((err) => alive && setError(err.message || "Unable to load the organisation."));
    return () => {
      alive = false;
    };
  }, []);

  // Run a change, then reload so the screen always shows what the server holds.
  const run = async (action) => {
    try {
      await action();
      setError("");
      await load();
    } catch (err) {
      setError(err.message || "Request failed.");
    }
  };

  const toggle = (item, update) =>
    run(() => update(item.code, { status: item.status === "active" ? "inactive" : "active" }));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink">Organisation</h1>
        <p className="mt-1 text-sm text-ink-3">
          Departments and the roles inside them. A role&apos;s clearance and permissions decide what
          its members can read and manage; documents add explicit grants on top.
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded-control border border-danger/30 bg-danger-soft p-4 text-sm text-danger">
          {error}
        </p>
      )}

      {/* Add department */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          run(async () => {
            await createDepartment(deptForm);
            setDeptForm({ code: "", name: "" });
          });
        }}
        className="flex flex-col gap-3 rounded-card border border-line bg-surface p-5 shadow-card sm:flex-row sm:items-end"
      >
        <label className="flex-1 text-sm font-medium text-ink-2">
          Department code
          <input
            className={inputCls}
            value={deptForm.code}
            onChange={(e) => setDeptForm({ ...deptForm, code: e.target.value.toUpperCase() })}
            placeholder="OPS"
            required
          />
        </label>
        <label className="flex-2 text-sm font-medium text-ink-2">
          Department name
          <input
            className={inputCls}
            value={deptForm.name}
            onChange={(e) => setDeptForm({ ...deptForm, name: e.target.value })}
            placeholder="Operations"
            required
          />
        </label>
        <button className="rounded-control bg-brand px-5 py-2.5 text-sm font-semibold text-on-brand hover:bg-brand-hover">
          Add department
        </button>
      </form>

      {departments.map((dept) => {
        const deptRoles = roles.filter((r) => r.department_code === dept.code);
        return (
          <section key={dept.code} className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
            <div className="flex items-center justify-between gap-4 px-6 py-4">
              <div>
                <h2 className="text-base font-semibold text-ink">
                  {dept.name}{" "}
                  <span className="ml-1 text-xs font-medium text-ink-3">{dept.code}</span>
                </h2>
                {dept.status !== "active" && (
                  <span className="text-xs font-semibold text-danger">Inactive</span>
                )}
              </div>
              <button
                type="button"
                onClick={() => toggle(dept, updateDepartment)}
                className={`${linkBtn} ${dept.status === "active" ? "text-danger" : "text-success"}`}
              >
                {dept.status === "active" ? "Deactivate" : "Activate"}
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-175 text-left">
                <thead>
                  <tr className="border-y border-line bg-surface-2 text-xs font-semibold uppercase tracking-wider text-ink-3">
                    <th className="px-6 py-3">Role</th>
                    <th className="px-6 py-3">Clearance</th>
                    <th className="px-6 py-3">Permissions</th>
                    <th className="px-6 py-3 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {deptRoles.length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-6 py-6 text-center text-sm text-ink-3">
                        No roles yet.
                      </td>
                    </tr>
                  )}
                  {deptRoles.map((role) => (
                    <tr key={role.code}>
                      <td className="px-6 py-3 text-sm font-medium text-ink">{role.name}</td>
                      <td className="px-6 py-3">
                        <select
                          aria-label={`Clearance for ${role.name}`}
                          value={role.clearance}
                          onChange={(e) =>
                            run(() => updateRole(role.code, { clearance: e.target.value }))
                          }
                          className={`${inputCls} w-40 capitalize`}
                        >
                          {CLEARANCES.map((c) => (
                            <option key={c} value={c}>{c}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-6 py-3">
                        <div className="flex flex-wrap gap-1.5">
                          {role.permissions.length === 0 && (
                            <span className="text-sm text-ink-3">None</span>
                          )}
                          {role.permissions.map((p) => (
                            <span key={p} className="rounded-full bg-brand-tint px-2.5 py-1 text-micro font-medium text-brand-text">
                              {PERMISSION_LABELS[p] ?? p}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-6 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => toggle(role, updateRole)}
                          className={`${linkBtn} ${role.status === "active" ? "text-danger" : "text-success"}`}
                        >
                          {role.status === "active" ? "Deactivate" : "Activate"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}

      {/* Add role */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          run(async () => {
            await createRole(roleForm);
            setRoleForm({ ...roleForm, code: "", name: "" });
          });
        }}
        className="grid gap-3 rounded-card border border-line bg-surface p-5 shadow-card sm:grid-cols-5 sm:items-end"
      >
        <label className="text-sm font-medium text-ink-2">
          Department
          <select
            className={`${inputCls}`}
            value={roleForm.department_code}
            onChange={(e) => setRoleForm({ ...roleForm, department_code: e.target.value })}
            required
          >
            <option value="">Select…</option>
            {departments.filter((d) => d.status === "active").map((d) => (
              <option key={d.code} value={d.code}>{d.name}</option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium text-ink-2">
          Role code
          <input
            className={inputCls}
            value={roleForm.code}
            onChange={(e) => setRoleForm({ ...roleForm, code: e.target.value.toUpperCase() })}
            placeholder="OPS_LEAD"
            required
          />
        </label>
        <label className="text-sm font-medium text-ink-2">
          Role name
          <input
            className={inputCls}
            value={roleForm.name}
            onChange={(e) => setRoleForm({ ...roleForm, name: e.target.value })}
            placeholder="Operations Lead"
            required
          />
        </label>
        <label className="text-sm font-medium text-ink-2">
          Clearance
          <select
            className={`${inputCls} capitalize`}
            value={roleForm.clearance}
            onChange={(e) => setRoleForm({ ...roleForm, clearance: e.target.value })}
          >
            {CLEARANCES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
        <button className="rounded-control bg-brand px-5 py-2.5 text-sm font-semibold text-on-brand hover:bg-brand-hover">
          Add role
        </button>
      </form>
    </div>
  );
}
