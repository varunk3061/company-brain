"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BuildingIcon, FolderIcon, GridIcon, ShieldIcon, UsersIcon } from "./icons";
import { NAV_ITEMS } from "./data";

const ICONS = {
  grid: GridIcon,
  users: UsersIcon,
  folder: FolderIcon,
  shield: ShieldIcon,
  org: BuildingIcon,
};

export default function AdminSidebar({ open, onNavigate, permissions = [] }) {
  const pathname = usePathname();

  const isActive = (href) =>
    href === "/admin" ? pathname === "/admin" : pathname.startsWith(href);

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-30 flex w-72 shrink-0 flex-col border-r border-line bg-surface pt-18 transition-transform duration-200 lg:static lg:z-auto lg:translate-x-0 lg:pt-0 ${
        open ? "translate-x-0" : "-translate-x-full"
      }`}
    >
      <div className="border-b border-line px-7 py-6">
        <p className="text-micro font-semibold uppercase tracking-wider text-brand-text">
          Administration
        </p>
        <p className="mt-1 text-base font-bold text-ink">Control Center</p>
      </div>

      <nav aria-label="Admin" className="flex-1 space-y-1 overflow-y-auto px-4 py-5">
        {NAV_ITEMS.filter((item) => permissions.includes(item.permission)).map((item) => {
          const Icon = ICONS[item.icon];
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-3 rounded-control px-4 py-3 text-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand ${
                active
                  ? "bg-brand-tint font-semibold text-brand-text"
                  : "font-medium text-ink-2 hover:bg-surface-2 hover:text-ink"
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