import Badge from "./Badge";

// Small pill for a single control or card.
export function ComingSoonBadge({ label = "Coming Soon" }) {
  return <Badge tone="brand">{label}</Badge>;
}

// Banner for a whole area that is planned but not built.
export function ComingSoonNotice({ title, children }) {
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-card border border-brand/30 bg-brand-tint p-4 text-left"
    >
      <ComingSoonBadge />
      <div className="min-w-0">
        <p className="text-sm font-semibold text-ink">{title}</p>
        {children && <p className="mt-0.5 text-sm text-ink-2">{children}</p>}
      </div>
    </div>
  );
}
