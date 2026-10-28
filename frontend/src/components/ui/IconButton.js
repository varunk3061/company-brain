// Compact icon-only action button for table rows.
// `label` is required: it is the accessible name and the hover tooltip, so the action stays clear without text.
const TONES = {
  brand: "text-brand-text hover:bg-brand-tint",
  danger: "text-danger hover:bg-danger-soft",
  success: "text-success hover:bg-success-soft",
  neutral: "text-ink-3 hover:bg-surface-3 hover:text-ink",
};

export default function IconButton({ icon: Icon, label, tone = "neutral", onClick, disabled = false, busy = false }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-control transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:cursor-not-allowed disabled:opacity-50 ${TONES[tone] ?? TONES.neutral}`}
    >
      <Icon className={`h-4 w-4 ${busy ? "animate-pulse" : ""}`} aria-hidden="true" />
    </button>
  );
}
