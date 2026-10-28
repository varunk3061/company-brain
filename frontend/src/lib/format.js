import { capitalizeName } from "@/lib/utils";

// Display helpers: data is stored as entered, but always shown consistently.

// "priya sharma" -> "Priya Sharma"
export const displayName = (value) => capitalizeName(value ?? "");

// "needs_review" / "blocked" -> "Needs Review" / "Blocked"
export const titleCase = (value = "") =>
  String(value)
    .replace(/[_-]+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());

// "document.access.update" -> "Document Access Update"
export const actionLabel = (value = "") => titleCase(String(value).replace(/\./g, " "));
