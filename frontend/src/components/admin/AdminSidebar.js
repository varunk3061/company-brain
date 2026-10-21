"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FolderIcon, GridIcon, ShieldIcon, UsersIcon } from "./icons";
import { NAV_ITEMS } from "./data";

const ICONS = {
  grid: GridIcon,
  users: UsersIcon,
  folder: FolderIcon,
  shield: ShieldIcon,
};

export default function AdminSidebar({ open, onNavigate }) {
  const pathname = usePathname();

  const isActive = (href) =>
    href === "/admin" ? pathname === "/admin" : pathname.startsWith(href);

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-30 flex w-72 shrink-0 flex-col border-r border-slate-200 bg-white pt-18 transition-transform duration-200 lg:static lg:z-auto lg:translate-x-0 lg:pt-0 ${
        open ? "translate-x-0" : "-translate-x-full"
      }`}
    >
      <div className="border-b border-slate-100 px-7 py-6">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-indigo-600">
          Administration
        </p>
        <p className="mt-1 text-base font-bold text-slate-900">Control Center</p>
      </div>

      <nav aria-label="Admin" className="flex-1 space-y-1 overflow-y-auto px-4 py-5">
        {NAV_ITEMS.map((item) => {
          const Icon = ICONS[item.icon];
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-3 rounded-xl px-4 py-3 text-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                active
                  ? "bg-indigo-50 font-semibold text-indigo-700"
                  : "font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              <Icon className="h-4.5 w-4.5" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}