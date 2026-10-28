const TONES = {
  success: "bg-success-soft text-success",
  info: "bg-info-soft text-info",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger",
  brand: "bg-brand-tint text-brand-text",
  neutral: "bg-surface-3 text-ink-2",
  "cat-2": "bg-cat-2-soft text-cat-2",
  "cat-3": "bg-cat-3-soft text-cat-3",
  "cat-4": "bg-cat-4-soft text-cat-4",
};

// Always carries text, so meaning never depends on colour alone.
export default function Badge({ tone = "neutral", children }) {
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-1 text-micro font-medium ${TONES[tone] ?? TONES.neutral}`}
    >
      {children}
    </span>
  );
}

const CLASSIFICATION_TONE = {
  public: "success",
  internal: "info",
  confidential: "warning",
  restricted: "danger",
};

export function ClassificationBadge({ value }) {
  return (
    <Badge tone={CLASSIFICATION_TONE[value] ?? "danger"}>
      {value ? value.charAt(0).toUpperCase() + value.slice(1) : "Restricted"}
    </Badge>
  );
}
