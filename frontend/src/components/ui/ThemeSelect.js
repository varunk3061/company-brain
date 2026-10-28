"use client";

import { useSyncExternalStore } from "react";
import { DEFAULT_THEME } from "@/config/theme";
import { applyTheme, readTheme, subscribeTheme } from "@/lib/theme";

const OPTIONS = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

// Appearance picker for the profile menu.
export default function ThemeSelect() {
  const theme = useSyncExternalStore(subscribeTheme, readTheme, () => DEFAULT_THEME);

  return (
    <div role="radiogroup" aria-label="Appearance" className="px-4 py-3">
      <p className="mb-2 text-micro font-semibold uppercase tracking-wider text-ink-3">
        Appearance
      </p>
      <div className="grid grid-cols-3 gap-1 rounded-control bg-surface-3 p-1">
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={theme === option.value}
            onClick={() => applyTheme(option.value)}
            className={`rounded-control px-2 py-1.5 text-xs font-semibold transition ${
              theme === option.value
                ? "bg-surface text-ink shadow-card"
                : "text-ink-3 hover:text-ink"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
