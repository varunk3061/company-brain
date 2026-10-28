"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import AdminSidebar from "./AdminSidebar";
import { BrainIcon, ChevronDownIcon, LogOutIcon, MenuIcon } from "./icons";
import { getMyProfile } from "@/services/authService";
import { clearSession } from "@/services/http";
import ThemeSelect from "@/components/ui/ThemeSelect";
import { displayName } from "@/lib/format";
import { ADMIN_PERMISSIONS } from "./data";

function getInitials(name = "") {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export default function AdminShell({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  // controls the signout confirmation modal.
  const [showSignOutModal, setShowSignOutModal] = useState(false);

  const menuRef = useRef(null);
  const router = useRouter();
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    // A 401 is handled in services/http.js (session cleared, redirect to /login).
    getMyProfile()
      .then((me) => {
        const isAdmin = ADMIN_PERMISSIONS.some((p) => me.permissions.includes(p));
        if (isAdmin) setProfile(me);
        else router.replace("/dashboard");
      })
      .catch(() => {});
  }, [router]);

  // modal function
  const handleSignOutClick = () => {
    setMenuOpen(false);
    setShowSignOutModal(true);
  };

  // Cancel sign-out
  const handleCancelSignOut = () => {
    setShowSignOutModal(false);
  };

  // Sign out after confirmation
  const handleSignOut = () => {
    clearSession();

    setShowSignOutModal(false);
    router.replace("/login");
  };

  useEffect(() => {
    const onClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target))
        setMenuOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  // ---------------------------------------------------------------------------------------------------------------------------------

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-surface text-ink">
      {/* Header */}
      <header className="relative z-40 flex h-18 shrink-0 items-center justify-between border-b border-line bg-surface px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setSidebarOpen((o) => !o)}
            aria-label="Toggle sidebar"
            className="rounded-control p-2 text-ink-3 hover:bg-surface-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand lg:hidden"
          >
            <MenuIcon className="h-5 w-5" />
          </button>
          <div className="flex h-10 w-10 items-center justify-center rounded-control bg-brand text-on-brand shadow-card">
            <BrainIcon className="h-5 w-5" />
          </div>
          <span className="text-lg font-bold tracking-tight">
            The Company Brain
          </span>
          <span className="hidden rounded-full border border-brand/30 bg-brand-tint px-3 py-1 text-micro font-medium text-brand-text sm:inline">
            Administration
          </span>
        </div>

        <div ref={menuRef} className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((o) => !o)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            className="flex items-center gap-3 rounded-control px-2 py-1.5 transition hover:bg-surface-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-brand text-xs font-bold text-on-brand">
              {profile ? getInitials(displayName(profile.name)) : "…"}
            </span>
            <span className="hidden text-left leading-tight sm:block">
              <span className="block text-sm font-semibold text-ink">
                {profile ? displayName(profile.name) : "Loading…"}
              </span>
              <span className="block text-xs text-ink-3">
                {profile
                  ? [profile.role_name]
                      .filter(Boolean)
                      .join(" • ")
                  : ""}
              </span>
            </span>
            <ChevronDownIcon className="h-4 w-4 text-ink-3" />
          </button>

          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 top-full mt-2 w-72 rounded-control border border-line bg-surface p-1.5 shadow-card"
            >
              {profile && (
                <div className="border-b border-line px-4 py-3">
                  <p className="text-sm font-semibold text-ink">{displayName(profile.name)}</p>
                  <p className="text-xs text-ink-3">{profile.email}</p>
                  <p className="mt-1 text-xs text-ink-3">{profile.role_name} · {profile.department_name}</p>
                </div>
              )}
              <ThemeSelect />
              <div className="my-1 border-t border-line" />
              <button
                type="button"
                role="menuitem"
                onClick={handleSignOutClick}
                className="flex w-full items-center gap-2 rounded-control px-3 py-2 text-sm text-ink-2 transition hover:bg-danger-soft hover:text-danger"
              >
                <LogOutIcon className="h-4 w-4 text-ink-3" />
                Sign Out
              </button>
            </div>
          )}
        </div>
      </header>

      <div className="relative flex min-h-0 flex-1">
        {sidebarOpen && (
          <button
            type="button"
            aria-label="Close sidebar"
            onClick={() => setSidebarOpen(false)}
            className="fixed inset-0 z-20 bg-overlay lg:hidden"
          />
        )}

        <AdminSidebar
          permissions={profile?.permissions ?? []}
          open={sidebarOpen}
          onNavigate={() => setSidebarOpen(false)}
        />

        <main className="scrollbar-stable min-w-0 flex-1 overflow-y-auto bg-surface-2 px-4 py-8 sm:px-8 lg:px-10">
          <div className="mx-auto max-w-6xl">{children}</div>
        </main>
      </div>

      {/* Admin Sign Out Confirmation Modal */}
      {showSignOutModal && (
        <div
          className="fixed inset-0 z-100 flex items-center justify-center bg-overlay px-4 backdrop-blur-sm"
          onClick={handleCancelSignOut}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="admin-signout-title"
            className="w-full max-w-md rounded-card border border-line bg-surface p-6 shadow-pop"
            onClick={(event) => event.stopPropagation()}
          >
            {/* Icon */}
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-danger-soft">
              <LogOutIcon className="h-7 w-7 text-danger" />
            </div>

            {/* Title */}
            <h2
              id="admin-signout-title"
              className="mt-4 text-center text-xl font-semibold text-ink"
            >
              Sign out?
            </h2>

            {/* Description */}
            <p className="mt-2 text-center text-sm leading-6 text-ink-3">
              Are you sure you want to sign out of the Company Brain Admin
              Security Control Center?
            </p>

            {/* Buttons */}
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={handleCancelSignOut}
                className="rounded-control border border-line px-5 py-2.5 text-sm font-medium text-ink-2 transition hover:bg-surface-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-line-strong"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleSignOut}
                className="flex items-center gap-2 rounded-control bg-danger px-5 py-2.5 text-sm font-medium text-on-danger transition hover:bg-danger-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-danger"
              >
                <LogOutIcon className="h-4 w-4" />
                Sign out
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
