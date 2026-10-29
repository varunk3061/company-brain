"use client";

import { Trash2 } from "lucide-react";
import { GlobeIcon, PlusIcon } from "./icons";
import { ComingSoonBadge } from "@/components/ui/ComingSoon";
import { FEATURES } from "@/config/features";
import { titleCase } from "@/lib/format";

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  profile,
  documentCount,
  open,
}) {
  return (
    <aside
      className={`fixed inset-y-0 left-0 z-30 flex w-80 shrink-0 flex-col border-r border-line bg-surface pt-18 transition-transform duration-200 lg:static lg:z-auto lg:translate-x-0 lg:pt-0 ${
        open ? "translate-x-0" : "-translate-x-full"
      }`}
    >
      {/* New query */}
      <div className="border-b border-line p-5">
        <button
          type="button"
          onClick={onNew}
          disabled={!FEATURES.questionAnswering}
          className="flex w-full items-center justify-center gap-2 rounded-control bg-brand px-4 py-3 text-sm font-semibold text-on-brand shadow-card transition hover:bg-brand-hover disabled:opacity-50"
        >
          <PlusIcon className="h-4 w-4" />
          New Knowledge Query
        </button>
      </div>

      {/* Scope: read-only until scope filtering exists */}
      {/* <div className="border-b border-line px-5 py-5">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wider text-ink-3">
            Knowledge Scope
          </p>
          {!FEATURES.scopeFilter && <ComingSoonBadge label="Filter Coming Soon" />}
        </div>
        <div className="flex items-center gap-2.5 rounded-control border border-line bg-surface-2 px-3.5 py-2.5 text-sm text-ink">
          <GlobeIcon className="h-4 w-4 shrink-0 text-info" />
          <span>
            All documents you can access
            {typeof documentCount === "number" && (
              <span className="text-ink-3"> ({documentCount})</span>
            )}
          </span>
        </div>
      </div> */}

      {/* Recent queries */}
      <nav aria-label="Recent queries" className="min-h-0 flex-1 overflow-y-auto px-3 py-5">
        <h2 className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-ink-3">
          Recent Queries
        </h2>
        {conversations.length === 0 ? (
          <p className="px-3 text-sm text-ink-3">No queries yet.</p>
        ) : (
          <ul className="space-y-1">
            {conversations.map((c) => {
              const convId = c.id || c._id;
              const isActive = convId === activeId;
              return (
                <li key={convId} className="group relative flex items-center">
                  <button
                    type="button"
                    onClick={() => onSelect(convId)}
                    aria-current={isActive ? "true" : undefined}
                    className={`w-full rounded-control py-2.5 pl-3 pr-9 text-left text-sm leading-snug transition ${
                      isActive
                        ? "bg-brand-tint font-medium text-brand-text"
                        : "text-ink-2 hover:bg-surface-2 hover:text-ink"
                    }`}
                  >
                    <span className="block truncate">{c.title}</span>
                  </button>
                  {onDelete && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(c);
                      }}
                      aria-label={`Delete ${c.title}`}
                      title="Delete query"
                      className={`absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-1.5 text-ink-3 transition hover:bg-danger-soft hover:text-danger focus:opacity-100 ${
                        isActive
                          ? "opacity-70 hover:opacity-100"
                          : "opacity-0 group-hover:opacity-100"
                      }`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </nav>

      {/* Real access level from the user's role */}
      <div className="flex items-center gap-2 border-t border-line px-6 py-4 text-xs text-ink-3">
        <span className="h-2 w-2 rounded-full bg-success" />
        <span>
          {/* Clearance:{" "} */}
          {/* <span className="font-semibold text-ink-2">
            {profile ? titleCase(profile.clearance) : "—"}
          </span> */}
          {profile && <> · {profile.department_name}</>}
        </span>
      </div>
    </aside>
  );
}
