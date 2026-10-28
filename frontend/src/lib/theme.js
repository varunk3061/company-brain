import { DEFAULT_THEME, THEMES, THEME_STORAGE_KEY } from "@/config/theme";

// Current theme as applied to <html> (set by the server default or public/theme-init.js).
export function readTheme() {
  const applied = document.documentElement.getAttribute("data-theme");
  return THEMES.includes(applied) ? applied : DEFAULT_THEME;
}

// UI-only for now: the choice lives in this browser, not on the user's account.
export function applyTheme(theme) {
  if (!THEMES.includes(theme)) return;
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {}
}

// Lets React subscribe to theme changes (see ThemeSelect).
export function subscribeTheme(callback) {
  const observer = new MutationObserver(callback);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });
  return () => observer.disconnect();
}
