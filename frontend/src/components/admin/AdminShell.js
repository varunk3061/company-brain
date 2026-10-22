"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import AdminSidebar from "./AdminSidebar";
import { BrainIcon, ChevronDownIcon, LogOutIcon, MenuIcon } from "./icons";
import { getAdminProfile } from "@/services/authService";

function getInitials(name = "") {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function formatRole(role = "") {
  return role === "admin"
    ? "Administrator"
    : role.charAt(0).toUpperCase() + role.slice(1);
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
    getAdminProfile()
      .then(setProfile)
      .catch((err) => {
        if (err.message === "NOT_AUTHENTICATED") {
          localStorage.removeItem("access_token");
          sessionStorage.removeItem("access_token");
          router.replace("/login");
        }
      });
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
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_role");

    sessionStorage.removeItem("access_token");
    sessionStorage.removeItem("user_role");

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
    <div className="flex h-screen flex-col overflow-hidden bg-white text-slate-900">
      {/* Header */}
      <header className="relative z-40 flex h-18 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setSidebarOpen((o) => !o)}
            aria-label="Toggle sidebar"
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 lg:hidden"
          >
            <MenuIcon className="h-5 w-5" />
          </button>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-200">
            <BrainIcon className="h-5 w-5" />
          </div>
          <span className="text-lg font-bold tracking-tight">
            The Company Brain
          </span>
          <span className="hidden rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-[11px] font-medium text-indigo-700 sm:inline">
            Admin Security Control Center
          </span>
        </div>

        <div ref={menuRef} className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((o) => !o)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            className="flex items-center gap-3 rounded-xl px-2 py-1.5 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
              {profile ? getInitials(profile.name) : "…"}
            </span>
            <span className="hidden text-left leading-tight sm:block">
              <span className="block text-sm font-semibold text-slate-800">
                {profile?.name ?? "Loading…"}
              </span>
              <span className="block text-xs text-slate-500">
                {profile
                  ? [formatRole(profile.role), profile.department]
                      .filter(Boolean)
                      .join(" • ")
                  : ""}
              </span>
            </span>
            <ChevronDownIcon className="h-4 w-4 text-slate-400 cursor-pointer" />
          </button>

          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 top-full mt-2 w-48 rounded-xl border border-slate-200 bg-white p-1.5 shadow-lg"
            >
              <button
                type="button"
                role="menuitem"
                onClick={handleSignOutClick}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-700 transition hover:bg-red-50 hover:text-red-600 cursor-pointer"
              >
                <LogOutIcon className="h-4 w-4 text-slate-500" />
                Sign out
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
            className="fixed inset-0 z-20 bg-slate-900/30 lg:hidden"
          />
        )}

        <AdminSidebar
          open={sidebarOpen}
          onNavigate={() => setSidebarOpen(false)}
        />

        <main className="min-w-0 flex-1 overflow-y-auto bg-slate-50 px-4 py-8 sm:px-8 lg:px-10">
          <div className="mx-auto max-w-6xl">{children}</div>
        </main>
      </div>

      {/* Admin Sign Out Confirmation Modal */}
      {showSignOutModal && (
        <div
          className="fixed inset-0 z-100 flex items-center justify-center bg-slate-900/50 px-4 backdrop-blur-sm"
          onClick={handleCancelSignOut}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="admin-signout-title"
            className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            {/* Icon */}
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-red-100">
              <LogOutIcon className="h-7 w-7 text-red-600" />
            </div>

            {/* Title */}
            <h2
              id="admin-signout-title"
              className="mt-4 text-center text-xl font-semibold text-slate-900"
            >
              Sign out?
            </h2>

            {/* Description */}
            <p className="mt-2 text-center text-sm leading-6 text-slate-500">
              Are you sure you want to sign out of the Company Brain Admin
              Security Control Center?
            </p>

            {/* Buttons */}
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={handleCancelSignOut}
                className="rounded-xl border border-slate-200 px-5 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 cursor-pointer"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleSignOut}
                className="flex items-center gap-2 rounded-xl bg-red-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-red-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 cursor-pointer"
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
