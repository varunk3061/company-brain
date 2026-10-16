"use client";

import { ChevronDownIcon, GlobeIcon, PlusIcon } from "./icons";
import { SCOPES, USER } from "./data";

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  scope,
  onScopeChange,
  open,
}) {
  return (
    <aside
      className={`fixed inset-y-0 left-0 z-30 flex w-80 shrink-0 flex-col border-r border-slate-200 bg-white pt-[72px] transition-transform duration-200 lg:static lg:z-auto lg:translate-x-0 lg:pt-0 ${
        open ? "translate-x-0" : "-translate-x-full"
      }`}
    >
      {/* New query */}
      <div className="border-b border-slate-100 p-5">
        <button
          type="button"
          onClick={onNew}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white shadow-md shadow-indigo-200 transition hover:bg-indigo-700 focus:outline-none focus-visible:ring-4 focus-visible:ring-indigo-200"
        >
          <PlusIcon className="h-4 w-4" />
          New Knowledge Query
        </button>
      </div>

      {/* Scope */}
      <div className="border-b border-slate-100 px-5 py-5">
        <label htmlFor="scope" className="mb-2 block text-xs font-semibold uppercase tracking-wider text-slate-500">
          Knowledge Scope
        </label>
        <div className="relative">
          <GlobeIcon className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-sky-500" />
          <select
            id="scope"
            value={scope}
            onChange={(e) => onScopeChange(e.target.value)}
            className="w-full appearance-none rounded-full border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-10 text-sm text-slate-800 outline-none transition focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-100"
          >
            {SCOPES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <ChevronDownIcon className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
        </div>
      </div>

      {/* Recent queries */}
      <nav aria-label="Recent queries" className="min-h-0 flex-1 overflow-y-auto px-3 py-5">
        <h2 className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
          Recent Queries
        </h2>
        <ul className="space-y-1">
          {conversations.map((c) => {
            const isActive = c.id === activeId;
            return (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => onSelect(c.id)}
                  aria-current={isActive ? "true" : undefined}
                  className={`w-full rounded-xl px-3 py-2.5 text-left text-sm leading-snug transition focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                    isActive
                      ? "bg-indigo-50 font-medium text-indigo-700"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                  }`}
                >
                  Q{c.num}: {c.title}
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Permission */}
      <div className="flex items-center gap-2 border-t border-slate-100 px-6 py-4 text-xs text-slate-500">
        <span className="h-2 w-2 rounded-full bg-emerald-500" />
        <span>
          Permission: <span className="font-semibold text-slate-700">{USER.permission}</span>
        </span>
      </div>
    </aside>
  );
}