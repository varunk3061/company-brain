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

// One standard, compact date/time format used in every table (viewer's local time zone).
// "2026-10-28T14:38:00Z" -> "28 Oct 2026, 08:08 PM"
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const pad = (n) => String(n).padStart(2, "0");

const toDate = (value) => {
  if (value === null || value === undefined || value === "") return null;
  // The API stores UTC but MongoDB returns naive datetimes ("2026-10-28T14:38:00"), so treat a
  // timestamp without a zone as UTC; otherwise the browser would read it as local time.
  const text = typeof value === "string" && /^\d{4}-\d{2}-\d{2}T[\d:.]+$/.test(value) ? `${value}Z` : value;
  const date = value instanceof Date ? value : new Date(text);
  return Number.isNaN(date.getTime()) ? null : date;
};

// "28 Oct 2026"
export const formatDate = (value) => {
  const date = toDate(value);
  return date ? `${pad(date.getDate())} ${MONTHS[date.getMonth()]} ${date.getFullYear()}` : "-";
};

// "08:08 PM"
export const formatTime = (value) => {
  const date = toDate(value);
  if (!date) return "-";
  const hours = date.getHours();
  return `${pad(hours % 12 || 12)}:${pad(date.getMinutes())} ${hours < 12 ? "AM" : "PM"}`;
};

// "28 Oct 2026, 08:08 PM"
export const formatDateTime = (value) => {
  const date = toDate(value);
  return date ? `${formatDate(date)}, ${formatTime(date)}` : "-";
};
