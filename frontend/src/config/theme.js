export const THEMES = ["light", "dark", "system"];

// Default for first-time visitors; each user can override it in the profile menu.
const requested = process.env.NEXT_PUBLIC_DEFAULT_THEME;

export const DEFAULT_THEME = THEMES.includes(requested) ? requested : "light";

export const THEME_STORAGE_KEY = "theme";
