import Link from "next/link";
import { ShieldIcon } from "../icons";

export default function AuditLogs() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Audit Logs</h1>
        <p className="mt-1 text-sm text-slate-500">
          Track admin actions, document access, and security events across the platform.
        </p>
      </div>

      <section className="flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white px-6 py-20 text-center shadow-sm">
        <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
          <ShieldIcon className="h-7 w-7" />
        </span>

        <span className="mt-6 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-indigo-700">
          Coming soon
        </span>

        <h2 className="mt-4 text-lg font-semibold text-slate-900">
          Audit logs are on the way
        </h2>
        <p className="mt-2 max-w-md text-sm text-slate-500">
          This page will show a complete history of who did what and when, including user
          changes, document ingestion, and permission updates.
        </p>

        <Link
          href="/admin"
          className="mt-8 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-200 transition hover:bg-indigo-700 focus:outline-none focus-visible:ring-4 focus-visible:ring-indigo-200"
        >
          Back to Dashboard
        </Link>
      </section>
    </div>
  );
}