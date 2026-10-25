import Badge from "./Badge";

const TONES = {
  EXEC: "neutral",
  IT: "info",
  HR: "cat-2",
  SALES: "success",
  FIN: "warning",
  LEGAL: "cat-3",
};

// `code` is a department code (IT, HR, ...); `children` is the label to show.
export default function DepartmentBadge({ code, children }) {
  return <Badge tone={TONES[code] ?? "neutral"}>{children ?? code ?? "-"}</Badge>;
}
