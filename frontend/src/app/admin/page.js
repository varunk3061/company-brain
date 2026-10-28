import SyncButton from "@/components/admin/SyncButton";
import DashboardOverview from "@/components/admin/DashboardOverview";

export default function AdminOverviewPage() {
  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Admin Overview</h1>
          {/* <p className="mt-1 text-sm text-ink-3">
            Real-time metrics, system health, and recent knowledge ingestion activity.
          </p> */}
        </div>
        {/* <SyncButton /> */}
      </div>

      <DashboardOverview />
    </div>
  );
}