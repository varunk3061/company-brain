import Link from "next/link";
import { FilePlusIcon, RefreshIcon, UserPlusIcon } from "./icons";

const EVENT_ICONS = {
  upload: { Icon: FilePlusIcon, tone: "text-indigo-500" },
  "user-add": { Icon: UserPlusIcon, tone: "text-emerald-500" },
  sync: { Icon: RefreshIcon, tone: "text-indigo-500" },
};

const DEPT_TONES = {
  HR: "bg-violet-50 text-violet-600",
  Engineering: "bg-sky-50 text-sky-600",
  IT: "bg-sky-50 text-sky-600",
  Finance: "bg-amber-50 text-amber-700",
  Support: "bg-rose-50 text-rose-600",
  Operations: "bg-teal-50 text-teal-700",
  System: "bg-slate-100 text-slate-600",
};

const STATUS_TONES = {
  Indexed: "bg-emerald-50 text-emerald-700",
  Success: "bg-emerald-50 text-emerald-700",
  Completed: "bg-emerald-50 text-emerald-700",
  Created: "bg-emerald-50 text-emerald-700",
  Registered: "bg-emerald-50 text-emerald-700",
  Failed: "bg-red-50 text-red-700",
};

const COLUMNS = ["Event / Action", "Actor / User", "Department", "Status", "Timestamp"];

export default function ActivityTable({ rows = [], emptyMessage = "No recent activity yet." }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-4 px-6 py-5">
        <h2 className="text-base font-semibold text-slate-900">Recent System Activity &amp; Ingestion</h2>
        <Link
          href="/admin/audit-logs"
          className="shrink-0 text-sm font-medium text-indigo-600 hover:text-indigo-700 focus:outline-none focus-visible:underline"
        >
          View All Audit Logs
        </Link>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-190 text-left">
          <thead>
            <tr className="border-y border-slate-200 bg-slate-50">
              {COLUMNS.map((c) => (
                <th key={c} scope="col" className="px-6 py-3.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.length === 0 && (
              <tr>
                <td colSpan={COLUMNS.length} className="px-6 py-10 text-center text-sm text-slate-400">
                  {emptyMessage}
                </td>
              </tr>
            )}
            {rows.map((r) => {
              const { Icon, tone } = EVENT_ICONS[r.type] ?? EVENT_ICONS.sync;
              return (
                <tr key={r.id} className="transition hover:bg-slate-50/60">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3 text-sm text-slate-800">
                      <Icon className={`h-4.5 w-4.5 shrink-0 ${tone}`} />
                      {r.event || "-"}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-700">{r.actor || "-"}</td>
                  <td className="px-6 py-4">
                    <span className={`inline-block rounded-full px-2.5 py-1 text-[11px] font-medium ${DEPT_TONES[r.dept] ?? DEPT_TONES.System}`}>
                      {r.dept || "-"}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-block rounded-full px-2.5 py-1 text-[11px] font-medium ${STATUS_TONES[r.status] ?? STATUS_TONES.Success}`}>
                      {r.status || "-"}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-400">{r.time || "-"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}