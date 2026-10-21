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
  indigo: "bg-indigo-50 text-indigo-600",
  emerald: "bg-emerald-50 text-emerald-600",
};

const NOTE_TONES = {
  good: "text-emerald-600",
  muted: "text-slate-500",
};

export default function StatCard({ stat }) {
  const Icon = ICONS[stat.icon];

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-slate-600">{stat.label}</p>
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${ICON_TONES[stat.iconTone]}`}>
          <Icon className="h-4.5 w-4.5" />
        </span>
      </div>
      <p className="mt-5 text-3xl font-bold tracking-tight text-slate-900">{stat.value}</p>
      <p className={`mt-2 flex items-center gap-1.5 text-xs ${NOTE_TONES[stat.note.tone]}`}>
        {stat.note.icon === "trend" && <TrendUpIcon className="h-3.5 w-3.5" />}
        {stat.note.icon === "check" && <CheckIcon className="h-3.5 w-3.5" />}
        {stat.note.text}
      </p>
    </div>
  );
}