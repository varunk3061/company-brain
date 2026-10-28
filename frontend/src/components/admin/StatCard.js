import { ComingSoonBadge } from "@/components/ui/ComingSoon";
import {
  ChatIcon,
  CheckIcon,
  FileCheckIcon,
  ShieldCheckIcon,
  TrendUpIcon,
  UsersIcon,
} from "./icons";

const ICONS = {
  users: UsersIcon,
  file: FileCheckIcon,
  chat: ChatIcon,
  shield: ShieldCheckIcon,
};

const ICON_TONES = {
  indigo: "bg-brand-tint text-brand-text",
  emerald: "bg-success-soft text-success",
};

const NOTE_TONES = {
  good: "text-success",
  muted: "text-ink-3",
};

export default function StatCard({ stat }) {
  const Icon = ICONS[stat.icon];

  return (
    <div className="rounded-card border border-line bg-surface p-6 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-ink-2">{stat.label}</p>
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-control ${ICON_TONES[stat.iconTone]}`}>
          <Icon className="h-4.5 w-4.5" />
        </span>
      </div>
      <div className="mt-5 flex min-h-9 items-center">
        {stat.comingSoon ? (
          <ComingSoonBadge />
        ) : (
          <p className="text-3xl font-bold tracking-tight text-ink">{stat.value}</p>
        )}
      </div>
      <p className={`mt-2 flex items-center gap-1.5 text-xs ${NOTE_TONES[stat.note.tone]}`}>
        {stat.note.icon === "trend" && <TrendUpIcon className="h-3.5 w-3.5" />}
        {stat.note.icon === "check" && <CheckIcon className="h-3.5 w-3.5" />}
        {stat.note.text}
      </p>
    </div>
  );
}