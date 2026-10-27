"use client";

import { BrainIcon, FileIcon } from "./icons";

// Supports **bold** and [[file-name.pdf]] links inside answer text.
function renderInline(text) {
  return text
    .split(/(\*\*[^*]+\*\*|\[\[[^\]]+\]\])/g)
    .filter(Boolean)
    .map((part, i) => {
      if (part.startsWith("**")) {
        return (
          <strong key={i} className="font-semibold text-ink">
            {part.slice(2, -2)}
          </strong>
        );
      }
      if (part.startsWith("[[")) {
        return (
          <span key={i}
            className="font-semibold text-brand-text "
          >
            {part.slice(2, -2)}
          </span>
        );
      }
      return part;
    });
}

function BotAvatar() {
  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand text-on-brand shadow-card">
      <BrainIcon className="h-5 w-5" />
    </div>
  );
}

export function UserMessage({ message, initials }) {
  return (
    <div className="flex items-start justify-end gap-3">
      <div className="max-w-4/5 rounded-card rounded-tr-md bg-brand px-5 py-3.5 text-chat leading-relaxed text-on-brand shadow-card sm:max-w-7/10">
        {message.text}
      </div>
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand text-xs font-bold text-on-brand">
        {initials}
      </div>
    </div>
  );
}

export function AssistantMessage({ message }) {
  const hasSources = message.sources && message.sources.length > 0;

  return (
    <div className="flex items-start gap-3">
      <BotAvatar />
      <div className="w-full max-w-3xl rounded-card rounded-tl-md border border-line bg-surface p-5 shadow-card">
        <div className="space-y-3 text-chat leading-relaxed text-ink-2">
          {message.paragraphs.map((p, i) => (
            <p key={i}>{renderInline(p)}</p>
          ))}
        </div>

        {hasSources && (
          <div className="mt-5 border-t border-line pt-4">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-3">
              Retrieved document citations (RAG engine)
            </h3>
            <div className="grid gap-3 sm:grid-cols-2">
              {message.sources.map((s, i) => {
                const docName = s.file || s.source || s.fileName || "Unknown document";
                return (
                  <div
                    key={`${docName}-${s.page}-${i}`}
                    className="flex items-center gap-3 rounded-control border border-line bg-surface-2 px-4 py-3 transition hover:border-brand/30 hover:bg-brand-tint/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                  >
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-danger-soft text-danger">
                      <FileIcon className="h-4.5 w-4.5" />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-ink">{docName}</span>
                      <span className="block text-xs text-ink-3">
                        Page {s.page ?? "Unknown"}
                      </span>
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function TypingMessage() {
  return (
    <div className="flex items-start gap-3" role="status" aria-label="The Company Brain is searching">
      <BotAvatar />
      <div className="flex items-center gap-1.5 rounded-card rounded-tl-md border border-line bg-surface px-5 py-4 shadow-card">
        <span className="h-2 w-2 animate-bounce rounded-full bg-line-strong anim-delay-1" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-line-strong anim-delay-2" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-line-strong" />
      </div>
    </div>
  );
}
