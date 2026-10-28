import Link from "next/link";
import Badge from "@/components/ui/Badge";
import DepartmentBadge from "@/components/ui/DepartmentBadge";
import { FilePlusIcon, RefreshIcon, UserPlusIcon } from "./icons";

const EVENT_ICONS = {
  upload: { Icon: FilePlusIcon, tone: "text-brand-text" },
  "user-add": { Icon: UserPlusIcon, tone: "text-success" },
  sync: { Icon: RefreshIcon, tone: "text-brand-text" },
};

const COLUMNS = ["Event", "Actor", "Department", "Status", "Time"];

export default function ActivityTable({ rows = [], emptyMessage = "No recent activity yet." }) {
  return (
    <section className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
      <div className="flex items-center justify-between gap-4 px-6 py-5">
        <h2 className="text-base font-semibold text-ink">Recent Activity</h2>
        <Link
          href="/admin/audit-logs"
          className="shrink-0 text-sm font-medium text-brand-text hover:underline"
        >
          View All Audit Logs
        </Link>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-190 text-left">
          <thead>
            <tr className="border-y border-line bg-surface-2">
              {COLUMNS.map((c) => (
                <th key={c} scope="col" className="px-6 py-3.5 text-xs font-semibold uppercase tracking-wider text-ink-3">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.length === 0 && (
              <tr>
                <td colSpan={COLUMNS.length} className="px-6 py-10 text-center text-sm text-ink-3">
                  {emptyMessage}
                </td>
              </tr>
            )}
            {rows.map((r) => {
              const { Icon, tone } = EVENT_ICONS[r.type] ?? EVENT_ICONS.sync;
              return (
                <tr key={r.id} className="transition hover:bg-surface-2/60">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3 text-sm text-ink">
                      <Icon className={`h-4.5 w-4.5 shrink-0 ${tone}`} />
                      {r.event || "-"}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-ink-2">{r.actor || "-"}</td>
                  <td className="px-6 py-4">
                    <DepartmentBadge code={r.dept}>{r.dept || "-"}</DepartmentBadge>
                  </td>
                  <td className="px-6 py-4">
                    <Badge tone={r.status === "Failed" ? "danger" : "success"}>{r.status || "-"}</Badge>
                  </td>
                  <td className="px-6 py-4 text-sm text-ink-3">{r.time || "-"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}